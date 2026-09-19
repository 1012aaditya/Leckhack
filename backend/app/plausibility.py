"""Catch impossible citations from the structure of the citation system itself.

The other stages ask a database whether a case exists. This one asks a
different question: *could* this citation exist at all?

Legal citations are not arbitrary strings. Reporters are published in
sequence over known date ranges, volumes fill in order, and pages are bounded.
Those constraints make some citations self-contradicting regardless of what any
database holds:

    42 F.2d 100 (2015)   F.2d stopped publishing in 1993
    58 F.3d 900 (1985)   F.3d did not begin until 1993
    12 F.5d 40           no such reporter has ever existed

None of those need a lookup, a model, or a network connection to reject. They
are wrong in the same way "the 13th month" is wrong.

Two things make this worth having beyond novelty:

1. **It covers what the corpus does not.** A partial corpus must stay silent
   about reporters it never loaded - the honest answer, but an unhelpful one.
   A structural contradiction is decidable for *every* reporter in
   reporters-db, so `900 F.2d 1 (2020)` gets a real answer even with no F.2d
   data at all.

2. **It is explainable.** "F.3d began publishing in 1993" is a reason a lawyer
   can check in seconds, unlike a similarity score.

The corpus-derived checks below (volume-to-year trend, page bounds) need real
data and stay silent on small samples rather than inventing a trend from three
cases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from reporters_db import REPORTERS

from .models import ExtractedCitation

# A volume-to-year trend fitted on a handful of points is noise. Below this many
# distinct volumes the check abstains.
MIN_VOLUMES_FOR_TREND = 20

# How far a cited year may sit from the trend before it is called suspicious.
# Reporter volumes are not perfectly uniform - a busy year fills more of them -
# so this is deliberately loose. It exists to catch a citation decades out of
# place, not to police a year either way.
TREND_TOLERANCE_YEARS = 6


class Severity(str, Enum):
    IMPOSSIBLE = "impossible"
    """Self-contradicting. No database can contain this."""

    SUSPICIOUS = "suspicious"
    """Out of line with the corpus, but not provably wrong."""

    OK = "ok"
    UNKNOWN = "unknown"
    """Not enough information to judge - never treated as a pass."""


@dataclass
class PlausibilityFinding:
    severity: Severity
    code: str
    message: str


@dataclass
class PlausibilityReport:
    findings: list[PlausibilityFinding] = field(default_factory=list)

    @property
    def severity(self) -> Severity:
        order = [Severity.IMPOSSIBLE, Severity.SUSPICIOUS, Severity.UNKNOWN, Severity.OK]
        for level in order:
            if any(f.severity is level for f in self.findings):
                return level
        return Severity.UNKNOWN

    @property
    def is_impossible(self) -> bool:
        return self.severity is Severity.IMPOSSIBLE

    @property
    def reason(self) -> str:
        for level in (Severity.IMPOSSIBLE, Severity.SUSPICIOUS):
            for finding in self.findings:
                if finding.severity is level:
                    return finding.message
        return ""

    def as_dict(self) -> dict:
        return {
            "severity": self.severity.value,
            "reason": self.reason,
            "findings": [
                {"severity": f.severity.value, "code": f.code, "message": f.message}
                for f in self.findings
            ],
        }


# ------------------------------------------------------------ reporter index

def _build_edition_index() -> dict[str, dict]:
    """Flatten reporters-db into edition -> {name, cite_type, start, end}.

    reporters-db groups editions under a family key (F.2d and F.3d both live
    under "F."), but citations name the edition, so the index is keyed that way.
    """
    index: dict[str, dict] = {}
    for entries in REPORTERS.values():
        for entry in entries:
            for edition, meta in (entry.get("editions") or {}).items():
                start, end = meta.get("start"), meta.get("end")
                index[edition] = {
                    "name": entry.get("name"),
                    "cite_type": entry.get("cite_type"),
                    "start_year": start.year if start else None,
                    "end_year": end.year if end else None,
                }
    return index


EDITIONS = _build_edition_index()


# -------------------------------------------------------------- basic checks

def check_reporter_known(citation: ExtractedCitation) -> PlausibilityFinding:
    reporter = (citation.reporter or "").strip()
    if not reporter:
        return PlausibilityFinding(
            Severity.UNKNOWN, "no_reporter", "No reporter could be read from this citation."
        )
    if reporter not in EDITIONS:
        return PlausibilityFinding(
            Severity.IMPOSSIBLE,
            "unknown_reporter",
            f"'{reporter}' is not a reporter that has ever been published.",
        )
    return PlausibilityFinding(
        Severity.OK, "reporter_known", f"{EDITIONS[reporter]['name']} is a real reporter."
    )


def check_year_in_lifespan(citation: ExtractedCitation) -> PlausibilityFinding:
    """The cited year must fall inside the reporter's publication run.

    This is the strongest check in the module: it is decidable for any reporter
    in reporters-db, needs no case law at all, and a failure is a genuine
    contradiction rather than an absence of evidence.
    """
    reporter = (citation.reporter or "").strip()
    edition = EDITIONS.get(reporter)
    if edition is None:
        return PlausibilityFinding(Severity.UNKNOWN, "no_edition", "")

    if not citation.year or not str(citation.year).isdigit():
        return PlausibilityFinding(
            Severity.UNKNOWN, "no_year", "No year was given, so the date could not be checked."
        )

    year = int(citation.year)
    start, end = edition["start_year"], edition["end_year"]
    name = edition["name"] or reporter

    if start and year < start:
        return PlausibilityFinding(
            Severity.IMPOSSIBLE,
            "year_before_reporter",
            f"{name} ({reporter}) did not begin publishing until {start}, "
            f"so a {year} case cannot appear in it.",
        )
    if end and year > end:
        return PlausibilityFinding(
            Severity.IMPOSSIBLE,
            "year_after_reporter",
            f"{name} ({reporter}) stopped publishing in {end}, "
            f"so a {year} case cannot appear in it.",
        )
    return PlausibilityFinding(
        Severity.OK,
        "year_in_range",
        f"{year} falls inside {reporter}'s publication run.",
    )


# ------------------------------------------------------ corpus-derived checks

def check_volume_year_trend(
    citation: ExtractedCitation, samples: list[tuple[int, int]]
) -> PlausibilityFinding:
    """Volumes fill in order, so volume and year move together.

    `samples` are (volume, year) pairs observed in the corpus. With enough of
    them a citation whose year is decades away from where its volume sits is
    worth flagging - a common shape for a fabricated cite, which tends to pair
    a plausible-looking volume with an arbitrary recent year.

    Abstains below MIN_VOLUMES_FOR_TREND: a trend fitted on a few points would
    manufacture confidence rather than measure it.
    """
    if not citation.year or not str(citation.year).isdigit() or not citation.volume:
        return PlausibilityFinding(Severity.UNKNOWN, "no_year_or_volume", "")

    distinct = {v for v, _ in samples}
    if len(distinct) < MIN_VOLUMES_FOR_TREND:
        return PlausibilityFinding(
            Severity.UNKNOWN,
            "insufficient_corpus",
            f"Only {len(distinct)} volume(s) of this reporter are held - too few to "
            f"judge whether the year fits the volume.",
        )

    try:
        volume = int(citation.volume)
    except ValueError:
        return PlausibilityFinding(Severity.UNKNOWN, "bad_volume", "")

    # Ordinary least squares on year ~ volume. Linear is the right model here:
    # reporters publish volumes at a roughly steady rate.
    n = len(samples)
    mean_v = sum(v for v, _ in samples) / n
    mean_y = sum(y for _, y in samples) / n
    denominator = sum((v - mean_v) ** 2 for v, _ in samples)
    if denominator == 0:
        return PlausibilityFinding(Severity.UNKNOWN, "degenerate_trend", "")

    slope = sum((v - mean_v) * (y - mean_y) for v, y in samples) / denominator
    intercept = mean_y - slope * mean_v
    expected = slope * volume + intercept
    drift = abs(int(citation.year) - expected)

    if drift > TREND_TOLERANCE_YEARS:
        return PlausibilityFinding(
            Severity.SUSPICIOUS,
            "volume_year_mismatch",
            f"Volume {volume} of {citation.reporter} was published around "
            f"{expected:.0f}, but this citation is dated {citation.year}.",
        )
    return PlausibilityFinding(
        Severity.OK, "volume_year_consistent", "The year fits the volume."
    )


def check_page_bounds(
    citation: ExtractedCitation, max_page: int | None
) -> PlausibilityFinding:
    """A page past the end of a volume we hold IN FULL cannot exist.

    Only meaningful for a complete volume. With a partial one the highest page
    we happen to hold is an artefact of what was downloaded, and treating it as
    the volume's last page would call real cases fabricated.
    """
    if max_page is None or not citation.page:
        return PlausibilityFinding(Severity.UNKNOWN, "no_page_data", "")
    try:
        page = int(citation.page)
    except ValueError:
        return PlausibilityFinding(Severity.UNKNOWN, "bad_page", "")

    if page > max_page:
        return PlausibilityFinding(
            Severity.IMPOSSIBLE,
            "page_beyond_volume",
            f"{citation.reporter} volume {citation.volume} ends at page {max_page}; "
            f"page {page} does not exist in it.",
        )
    return PlausibilityFinding(Severity.OK, "page_in_range", "The page is within the volume.")


# ------------------------------------------------------------------ assembly

class PlausibilityChecker:
    """Runs the structural checks, using corpus statistics where available."""

    def __init__(self, store=None) -> None:
        self._store = store

    def check(self, citation: ExtractedCitation) -> PlausibilityReport:
        if not citation.is_lookupable:
            return PlausibilityReport()

        findings = [
            check_reporter_known(citation),
            check_year_in_lifespan(citation),
        ]

        # A citation already proven impossible needs no further evidence, and
        # corpus statistics for a reporter that never existed are meaningless.
        if any(f.severity is Severity.IMPOSSIBLE for f in findings):
            return PlausibilityReport(findings)

        if self._store is not None:
            reporter = str(citation.reporter)
            findings.append(
                check_volume_year_trend(
                    citation, self._store.volume_year_samples(reporter)
                )
            )
            # covers() is true only for volumes loaded in full - see store.
            if self._store.covers(reporter, str(citation.volume)):
                findings.append(
                    check_page_bounds(
                        citation, self._store.max_page(reporter, str(citation.volume))
                    )
                )

        return PlausibilityReport(findings)


# ------------------------------------------------- citations nobody can parse

import re  # noqa: E402  (kept beside the scanner that uses it)

from reporters_db import JOURNALS, LAWS, VARIATIONS_ONLY  # noqa: E402

# A citation-shaped string: volume, reporter abbreviation, page.
#
# The reporter must contain a full stop. Nearly every real abbreviation has one
# (F.3d, U.S., N.E.2d, Cal. App.), and requiring it removes almost all the
# false positives that plain prose would otherwise throw up - "3 March 2020",
# "2 of 5 items", "12 Main Street 4".
_CANDIDATE = re.compile(
    r"\b(?P<volume>\d{1,4})\s+"
    r"(?P<reporter>[A-Z][A-Za-z0-9.']*(?:\s+[A-Z][A-Za-z0-9.']*){0,3})\s+"
    r"(?P<page>\d{1,5})\b"
)

def _all_known_citation_abbreviations() -> set[str]:
    """Every abbreviation that legitimately appears in a citation.

    Case reporters are not the whole of legal citation. Statutes and
    administrative codes (42 U.S.C. 1983) and law journals (58 Harv. L. Rev.
    12) are citation-shaped and entirely real, and calling one of them a
    fabricated reporter would be a conspicuous error - 42 U.S.C. § 1983 is
    among the most-cited provisions in American law. reporters-db ships LAWS
    and JOURNALS alongside REPORTERS, so all three are excluded.
    """
    known: set[str] = set(EDITIONS) | set(VARIATIONS_ONLY)
    for collection in (LAWS, JOURNALS):
        known |= set(collection)
        for entries in collection.values():
            for entry in entries if isinstance(entries, list) else [entries]:
                if isinstance(entry, dict):
                    known |= set(entry.get("variations") or {})
    # Bare prefixes, so a trailing section number does not defeat the match.
    known |= {abbrev.split(" §")[0].strip() for abbrev in list(known)}
    return known


_KNOWN_REPORTER_STRINGS = _all_known_citation_abbreviations()


@dataclass
class UnparsedCitation:
    """A citation-shaped string naming a reporter that does not exist."""

    raw: str
    volume: str
    reporter: str
    page: str
    start: int
    end: int


def find_invented_reporters(
    text: str, known_spans: list[tuple[int, int]]
) -> list[UnparsedCitation]:
    """Find citation-shaped strings whose reporter was never published.

    This exists because eyecite - correctly, for its own purpose - silently
    discards anything whose reporter it does not recognise. For a citation
    parser that is right. For a fabrication detector it is a blind spot: an AI
    that invents both the case *and* the reporter produces `12 F.5d 40`, which
    then never appears in the report at all. Saying nothing about a made-up
    citation is a worse failure than flagging it.

    `known_spans` are the offsets eyecite already claimed, so a real citation
    is never double-reported.
    """
    found: list[UnparsedCitation] = []

    for match in _CANDIDATE.finditer(text):
        start, end = match.span()
        if any(a < end and start < b for a, b in known_spans):
            continue

        reporter = match.group("reporter").strip()
        if "." not in reporter or len(reporter) > 25:
            continue
        if reporter in _KNOWN_REPORTER_STRINGS:
            # A real reporter eyecite declined for some other reason; not ours
            # to call fabricated.
            continue

        found.append(
            UnparsedCitation(
                raw=match.group(0).strip(),
                volume=match.group("volume"),
                reporter=reporter,
                page=match.group("page"),
                start=start,
                end=end,
            )
        )

    return found
