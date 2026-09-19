"""Turning lookups into the traffic-light report a user reads.

Currently wires stage 0 (extract) to stage 1 (existence). Stages 2 and 3 -
does the case support the claim, and is it still good law - slot in here.
"""

from __future__ import annotations

import asyncio

from .extract import extract_citations
from .models import (
    AuditReport,
    CitationReport,
    ExistenceStatus,
    ExtractedCitation,
    Verdict,
)
from .sources.base import CaseLawSource, LookupResult
from .sources.courtlistener import CourtListenerError

# Deliberately below the documented 60 valid citations/minute so a long
# document degrades gracefully instead of tripping a 429 mid-demo.
_MAX_CONCURRENT_LOOKUPS = 8


def _judge(
    citation: ExtractedCitation, result: LookupResult, authoritative: bool
) -> tuple[Verdict, str]:
    """Decide the traffic light and the sentence shown beside it.

    The `authoritative` flag carries real weight. Telling someone a case is
    fabricated is a serious claim, and a stand-in database that holds six
    sample cases has not earned the right to make it. When the source is not
    authoritative, a miss is reported as unverified rather than as fake.
    """
    if result.status is ExistenceStatus.UNCHECKED:
        if not citation.is_lookupable:
            return Verdict.UNKNOWN, "Short-form reference - points at the citation above it."
        return Verdict.UNKNOWN, result.detail or "Could not be checked."

    if result.status is ExistenceStatus.RESOLVED:
        match = result.matches[0]
        name = match.case_name or "this case"
        return Verdict.GREEN, f"Real case: {name}. Click through to read it."

    if result.status is ExistenceStatus.NOT_FOUND:
        if not authoritative:
            return (
                Verdict.UNKNOWN,
                "Not in the offline sample. Connect a live database to check this properly.",
            )
        return (
            Verdict.RED,
            "No case with this citation exists in a database of millions of decisions. "
            "This looks fabricated.",
        )

    if result.status is ExistenceStatus.AMBIGUOUS:
        return Verdict.AMBER, "This citation matches more than one case - it is ambiguous."

    if result.status is ExistenceStatus.BAD_REPORTER:
        return Verdict.AMBER, "That reporter is not one we recognise, so this cannot be checked."

    return Verdict.UNKNOWN, result.detail or "Could not be checked."


async def audit_text(text: str, source: CaseLawSource) -> AuditReport:
    """Run the full audit over a block of text."""
    citations = extract_citations(text)
    if not citations:
        return AuditReport.build([], source.name)

    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_LOOKUPS)
    authoritative = getattr(source, "is_authoritative", False)

    async def check(citation: ExtractedCitation) -> CitationReport:
        async with semaphore:
            try:
                result = await source.lookup(citation)
            except CourtListenerError as exc:
                # A database outage must never be reported as a fabricated
                # citation. Say plainly that the check did not run.
                return CitationReport(
                    citation=citation,
                    verdict=Verdict.UNKNOWN,
                    explanation=f"Could not check this citation: {exc}",
                )

        verdict, explanation = _judge(citation, result, authoritative)
        return CitationReport(
            citation=citation,
            existence=result.status,
            matches=result.matches,
            verdict=verdict,
            explanation=explanation,
        )

    reports = await asyncio.gather(*(check(c) for c in citations))
    return AuditReport.build(list(reports), source.name)
