"""Data shapes shared across the auditor.

The vocabulary here mirrors the three checks described in docs/features.md:
a citation is EXTRACTED from text, then checked for EXISTENCE, then for
SUPPORT, then for whether it is still good law.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Verdict(str, Enum):
    """Traffic light shown next to each citation."""

    GREEN = "green"
    AMBER = "amber"
    RED = "red"
    UNKNOWN = "unknown"


class ExistenceStatus(str, Enum):
    """Outcome of the stage 1 database lookup.

    Deliberately mirrors the CourtListener citation-lookup status codes so a
    live response maps onto this without interpretation:
    200 resolved, 404 valid format but no such case, 300 ambiguous,
    400 unrecognised reporter.
    """

    RESOLVED = "resolved"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    BAD_REPORTER = "bad_reporter"
    UNCHECKED = "unchecked"


class ExtractedCitation(BaseModel):
    """One citation as eyecite found it, before any lookup happens."""

    raw: str = Field(description="Text exactly as it appeared in the input.")
    normalized: str | None = Field(
        default=None, description="eyecite's corrected form, e.g. '531 U.S. 98'."
    )
    kind: str = Field(description="eyecite class name, e.g. FullCaseCitation.")
    volume: str | None = None
    reporter: str | None = None
    page: str | None = None
    year: str | None = None
    court: str | None = None
    plaintiff: str | None = None
    defendant: str | None = None
    pin_cite: str | None = None
    start: int = Field(description="Character offset of the citation in the input.")
    end: int

    @property
    def case_name(self) -> str | None:
        if self.plaintiff and self.defendant:
            return f"{self.plaintiff} v. {self.defendant}"
        return None

    @property
    def is_lookupable(self) -> bool:
        """Whether this citation carries enough to query a database.

        `Id.` and `supra` references point at an earlier citation rather than
        naming a case, so they are reported but not looked up.
        """
        return bool(self.volume and self.reporter and self.page)


class CaseMatch(BaseModel):
    """A real case found in the database."""

    case_name: str | None = None
    citation: str | None = None
    court: str | None = None
    date_filed: str | None = None
    url: str | None = Field(default=None, description="Link a judge can click.")
    opinion_id: int | None = None
    source: str = Field(description="Which database answered, e.g. 'courtlistener'.")


class CitationReport(BaseModel):
    """Everything known about one citation after the checks that have run."""

    citation: ExtractedCitation
    existence: ExistenceStatus = ExistenceStatus.UNCHECKED
    matches: list[CaseMatch] = Field(default_factory=list)
    verdict: Verdict = Verdict.UNKNOWN
    explanation: str = Field(
        default="", description="Plain-English sentence shown to the user."
    )


class AuditReport(BaseModel):
    """The whole document's result."""

    citations: list[CitationReport] = Field(default_factory=list)
    total: int = 0
    problems: int = 0
    unchecked: int = 0
    headline: str = ""
    source_used: str = ""

    @classmethod
    def build(cls, reports: list[CitationReport], source_used: str) -> "AuditReport":
        """Summarise the run.

        The headline distinguishes "checked and fine" from "not checked at
        all". Collapsing the two would have this tool overclaiming in exactly
        the way it exists to catch - a citation nobody could verify is not a
        citation that passed.
        """
        total = len(reports)
        problems = sum(1 for r in reports if r.verdict in (Verdict.RED, Verdict.AMBER))
        unchecked = sum(1 for r in reports if r.verdict is Verdict.UNKNOWN)
        checked = total - unchecked

        noun = "citation" if total == 1 else "citations"

        if total == 0:
            headline = "No case citations found in this text."
        elif problems:
            headline = f"{problems} of {total} {noun} have problems."
        elif unchecked == total:
            headline = (
                f"This {noun} could not be checked."
                if total == 1
                else f"None of the {total} {noun} could be checked."
            )
        elif unchecked:
            headline = (
                f"{checked} of {total} {noun} checked out; "
                f"{unchecked} could not be checked."
            )
        else:
            headline = f"All {total} {noun} checked out."

        return cls(
            citations=reports,
            total=total,
            problems=problems,
            unchecked=unchecked,
            headline=headline,
            source_used=source_used,
        )
