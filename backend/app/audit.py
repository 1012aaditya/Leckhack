"""The pipeline: extract, then check existence, support, and later treatment.

Each stage can be absent - no database, no opinion text, no citation graph -
and the report says so rather than guessing. That is the point: this tool is
supposed to distinguish "checked and fine" from "never checked", including
about itself.
"""

from __future__ import annotations

import asyncio

from .extract import claim_for, extract_citations, prepare_text
from .goodlaw import GoodLawReport, check_good_law
from .judge import Judge, Stance, judge_with_guard
from .models import (
    AuditReport,
    CitationReport,
    ExistenceStatus,
    ExtractedCitation,
    Verdict,
)
from .embeddings import Embedder
from .retrieval import search_opinion
from .sources.base import CaseLawSource, LookupResult
from .sources.courtlistener import CourtListenerError
from .store import Store

# Comfortably below CourtListener's 60 valid citations/minute so a long document
# degrades gracefully rather than tripping a 429 mid-demo.
MAX_CONCURRENT_LOOKUPS = 8
PASSAGES_PER_CLAIM = 4

_SEVERITY = {Verdict.GREEN: 0, Verdict.UNKNOWN: 1, Verdict.AMBER: 2, Verdict.RED: 3}


def _worst(*verdicts: Verdict) -> Verdict:
    return max(verdicts, key=lambda v: _SEVERITY[v])


class Auditor:
    """Runs the checks that the configured components make possible.

    `store`, `embedder` and `judge` are all optional. Without them stage 1 still
    runs on its own, which is a working product - it catches outright
    fabrication. The later stages are additive.
    """

    def __init__(
        self,
        source: CaseLawSource,
        store: Store | None = None,
        embedder: Embedder | None = None,
        judge: Judge | None = None,
    ) -> None:
        self.source = source
        self.store = store
        self.embedder = embedder
        self.judge = judge

    @property
    def can_check_support(self) -> bool:
        return all((self.store, self.embedder, self.judge))

    @property
    def can_check_good_law(self) -> bool:
        return self.store is not None

    # ------------------------------------------------------------------ stages

    async def _existence(self, citation: ExtractedCitation) -> tuple[LookupResult | None, str]:
        try:
            return await self.source.lookup(citation), ""
        except CourtListenerError as exc:
            # A database outage must never be presented as a fabricated
            # citation. Say the check did not run.
            return None, str(exc)

    def _support(self, claim: str, citation_key: str) -> tuple[dict | None, list[str]]:
        """Stage 2, synchronous - it is CPU and API bound, not IO-concurrent."""
        if not self.can_check_support or not claim:
            return None, []

        opinion = self.store.get_opinion(citation_key)
        if opinion is None or not opinion.text.strip():
            return None, ["We do not hold this opinion's text, so we could not check "
                          "whether the case says what was claimed."]

        passages = [
            chunk.text
            for chunk, _ in search_opinion(
                self.store, self.embedder, opinion.id, claim, k=PASSAGES_PER_CLAIM
            )
        ]
        finding = judge_with_guard(self.judge, claim, passages, opinion.text)

        notes: list[str] = []
        if opinion.is_synthetic:
            notes.append(
                "This opinion's text is synthetic demo data, not a real court record."
            )
        if not self.judge.is_model_based:
            notes.append(
                "Checked with the offline word-matching fallback, which is much weaker "
                "than the full check."
            )
        return finding.model_dump(mode="json"), notes

    def _good_law(self, citation_key: str) -> GoodLawReport | None:
        if not self.can_check_good_law:
            return None
        opinion = self.store.get_opinion(citation_key)
        if opinion is None:
            return None
        return check_good_law(self.store, opinion.id)

    # ----------------------------------------------------------------- verdict

    def _compose(
        self,
        citation: ExtractedCitation,
        result: LookupResult | None,
        error: str,
        support: dict | None,
        good_law: GoodLawReport | None,
    ) -> tuple[Verdict, str, list[str]]:
        notes: list[str] = []

        if error:
            return Verdict.UNKNOWN, f"Could not check this citation: {error}", notes

        if result is None or result.status is ExistenceStatus.UNCHECKED:
            if not citation.is_lookupable:
                return (
                    Verdict.UNKNOWN,
                    "Short-form reference - points at the citation above it.",
                    notes,
                )
            detail = result.detail if result else ""
            return Verdict.UNKNOWN, detail or "Could not be checked.", notes

        authoritative = result.authoritative
        if authoritative is None:
            authoritative = getattr(self.source, "is_authoritative", False)

        if result.status is ExistenceStatus.NOT_FOUND:
            if not authoritative:
                return (
                    Verdict.UNKNOWN,
                    result.detail
                    or "Not in the corpus we hold, so this could not be checked.",
                    notes,
                )
            # Prefer the source's own words: a local corpus knows exactly what
            # it covers, and claiming "a database of millions of decisions"
            # while holding three would be the overclaiming this tool exists
            # to catch.
            reason = result.detail or (
                "No case with this citation exists in the database checked."
            )
            return Verdict.RED, f"{reason} This looks fabricated.", notes

        if result.status is ExistenceStatus.AMBIGUOUS:
            return Verdict.AMBER, "This citation matches more than one case.", notes
        if result.status is ExistenceStatus.BAD_REPORTER:
            return (
                Verdict.AMBER,
                "That reporter is not one we recognise, so this cannot be checked.",
                notes,
            )

        # Resolved. Now the harder questions.
        name = result.matches[0].case_name if result.matches else "this case"
        verdict = Verdict.GREEN
        parts = [f"Real case: {name}."]

        if support is None:
            parts.append("We could not check whether it says what was claimed.")
        else:
            stance = Stance(support["stance"])
            if stance is Stance.SUPPORTS:
                parts.append("The opinion does support this claim.")
            elif stance is Stance.CONTRADICTS:
                verdict = _worst(verdict, Verdict.AMBER)
                parts.append("But the opinion appears to say the opposite.")
            elif stance is Stance.NOT_ADDRESSED:
                verdict = _worst(verdict, Verdict.AMBER)
                parts.append("But nothing in the opinion addresses this claim.")
            else:
                parts.append("Whether it supports the claim could not be settled.")

        if good_law is not None and good_law.has_negative_treatment:
            verdict = _worst(verdict, Verdict.AMBER)
            parts.append("A later case appears to have undercut it.")
        # When citing_count is 0 the good-law summary already says so, and the
        # UI renders that summary - a second note would just repeat it.

        return verdict, " ".join(parts), notes

    # -------------------------------------------------------------------- run

    async def run(self, text: str) -> AuditReport:
        cleaned = prepare_text(text)
        citations = extract_citations(cleaned)
        if not citations:
            return AuditReport.build([], self.source.name)

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_LOOKUPS)

        async def check(citation: ExtractedCitation) -> CitationReport:
            async with semaphore:
                result, error = await self._existence(citation)

            # Short forms (Id., supra) are never checked, so a "claimed" line
            # for them is noise at best and misleading at worst - the fallback
            # window can span several unrelated sentences.
            claim = claim_for(cleaned, citation) if citation.is_lookupable else ""
            key = f"{citation.volume} {citation.reporter} {citation.page}"

            support, good_law, notes = None, None, []
            resolved = result is not None and result.status is ExistenceStatus.RESOLVED
            if resolved and citation.is_lookupable:
                support, support_notes = await asyncio.to_thread(self._support, claim, key)
                notes.extend(support_notes)
                good_law = await asyncio.to_thread(self._good_law, key)

            verdict, explanation, verdict_notes = self._compose(
                citation, result, error, support, good_law
            )
            notes.extend(verdict_notes)

            return CitationReport(
                citation=citation,
                claim=claim,
                existence=result.status if result else ExistenceStatus.UNCHECKED,
                matches=result.matches if result else [],
                support=support,
                good_law=good_law.model_dump(mode="json") if good_law else None,
                verdict=verdict,
                explanation=explanation,
                notes=notes,
            )

        reports = await asyncio.gather(*(check(c) for c in citations))
        return AuditReport.build(list(reports), self.source.name)


async def audit_text(text: str, source: CaseLawSource, **kwargs) -> AuditReport:
    """Convenience wrapper for stage-1-only audits."""
    return await Auditor(source, **kwargs).run(text)
