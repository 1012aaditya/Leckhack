"""Stage 3: is the cited case still good law?

A case can be real, and can genuinely say what was claimed, and still be a bad
thing to rely on because a later court overruled it.

What this is NOT: Shepard's or KeyCite. Those are enormous commercial products
built on decades of editorial work. What this is: a scan of the opinions that
cite the target, looking for language that signals the case was overruled or
criticised. That is a useful warning and a poor guarantee, and the UI says so.
Overclaiming here is the fastest way to lose a legal reader's trust.
"""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, Field

from .quote_guard import verify_quote
from .retrieval import split_sentences
from .store import Store

# Phrases courts actually use when they discard or undercut earlier authority.
# Ordered strongest first; the first match wins.
_NEGATIVE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("overruled", re.compile(r"\b(overrul\w+|abrogat\w+|we\s+now\s+reject)\b", re.I)),
    ("superseded", re.compile(r"\b(supersed\w+|legislatively\s+overrul\w+)\b", re.I)),
    ("limited", re.compile(r"\b(limited\s+to\s+its\s+facts|declin\w+\s+to\s+extend|"
                           r"confin\w+\s+to\s+its\s+facts)\b", re.I)),
    ("criticized", re.compile(r"\b(criticiz\w+|criticis\w+|questioned|"
                              r"unpersuasive|we\s+disagree\s+with)\b", re.I)),
]

_POSITIVE = re.compile(r"\b(reaffirm\w+|follow\w+|adher\w+\s+to|consistent\s+with)\b", re.I)


class Treatment(str, Enum):
    OVERRULED = "overruled"
    SUPERSEDED = "superseded"
    LIMITED = "limited"
    CRITICIZED = "criticized"
    FOLLOWED = "followed"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


NEGATIVE_TREATMENTS = {
    Treatment.OVERRULED,
    Treatment.SUPERSEDED,
    Treatment.LIMITED,
    Treatment.CRITICIZED,
}


class TreatmentFinding(BaseModel):
    treatment: Treatment = Treatment.UNKNOWN
    citing_case: str | None = None
    citing_citation: str | None = None
    citing_url: str | None = None
    citing_date: str | None = None
    quote: str = ""
    quote_verified: bool = False


class GoodLawReport(BaseModel):
    checked: bool = False
    citing_count: int = 0
    findings: list[TreatmentFinding] = Field(default_factory=list)
    summary: str = ""

    @property
    def has_negative_treatment(self) -> bool:
        return any(f.treatment in NEGATIVE_TREATMENTS for f in self.findings)


def _mentions(sentence: str, citation: str, case_name: str | None) -> bool:
    if citation and citation.lower() in sentence.lower():
        return True
    if case_name:
        # "Bush v. Gore" is also referred to as just "Bush" in later opinions.
        lead = case_name.split(" v. ")[0].strip()
        if len(lead) > 3 and re.search(rf"\b{re.escape(lead)}\b", sentence, re.I):
            return True
    return False


def classify_treatment(
    citing_text: str, cited_citation: str, cited_case_name: str | None
) -> tuple[Treatment, str]:
    """Look for treatment language in the sentences that mention the case.

    Restricting to mentioning sentences matters: an opinion may overrule some
    other case entirely, and scanning the whole document for the word
    "overruled" would attribute that to the wrong target.
    """
    for sentence in split_sentences(citing_text):
        if not _mentions(sentence, cited_citation, cited_case_name):
            continue
        for label, pattern in _NEGATIVE_PATTERNS:
            if pattern.search(sentence):
                return Treatment(label), sentence
        if _POSITIVE.search(sentence):
            return Treatment.FOLLOWED, sentence
    return Treatment.NEUTRAL, ""


def check_good_law(store: Store, opinion_id: int) -> GoodLawReport:
    """Scan every opinion citing this one for negative treatment."""
    target = store.get_opinion_by_id(opinion_id)
    if target is None:
        return GoodLawReport(summary="Case not in the local store, so not checked.")

    citing = store.citing_opinions(opinion_id)
    if not citing:
        return GoodLawReport(
            checked=True,
            citing_count=0,
            summary=(
                "No later cases citing this one are held locally, so later treatment "
                "could not be checked."
            ),
        )

    findings: list[TreatmentFinding] = []
    for opinion in citing:
        treatment, quote = classify_treatment(
            opinion.text, target.citation, target.case_name
        )
        if treatment in (Treatment.NEUTRAL, Treatment.UNKNOWN):
            continue
        verified = bool(quote) and verify_quote(quote, opinion.text).verified
        findings.append(
            TreatmentFinding(
                treatment=treatment,
                citing_case=opinion.case_name,
                citing_citation=opinion.citation,
                citing_url=opinion.url,
                citing_date=opinion.date_filed,
                quote=quote if verified else "",
                quote_verified=verified,
            )
        )

    negative = [f for f in findings if f.treatment in NEGATIVE_TREATMENTS]
    if negative:
        worst = negative[0]
        summary = (
            f"A later case ({worst.citing_case or 'unknown'}) appears to have "
            f"{worst.treatment.value} this one. This is a warning signal, not a "
            f"substitute for a professional citator."
        )
    else:
        summary = (
            f"Scanned {len(citing)} later case(s) citing this one; no negative "
            f"treatment found. This is not a guarantee the case is still good law."
        )

    return GoodLawReport(
        checked=True, citing_count=len(citing), findings=findings, summary=summary
    )
