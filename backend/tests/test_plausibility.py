"""Structural checks: could this citation exist at all?

No database, no model, no network - these reason from the structure of the
citation system itself.
"""

import pytest

from app.extract import extract_citations, prepare_text
from app.plausibility import (
    EDITIONS,
    PlausibilityChecker,
    Severity,
    check_page_bounds,
    check_reporter_known,
    check_volume_year_trend,
    check_year_in_lifespan,
    find_invented_reporters,
)


def cite(text):
    return extract_citations(prepare_text(text))[0]


def test_reporter_index_is_populated():
    assert len(EDITIONS) > 1000
    assert EDITIONS["F.3d"]["start_year"] == 1993
    assert EDITIONS["F.2d"]["end_year"] == 1993


# ------------------------------------------------------- reporter lifespans


def test_year_before_the_reporter_existed_is_impossible():
    finding = check_year_in_lifespan(cite("See 58 F.3d 900 (1985)."))
    assert finding.severity is Severity.IMPOSSIBLE
    assert "1993" in finding.message


def test_year_after_the_reporter_ended_is_impossible():
    finding = check_year_in_lifespan(cite("See 42 F.2d 300 (2015)."))
    assert finding.severity is Severity.IMPOSSIBLE
    assert "stopped publishing" in finding.message


def test_year_inside_the_run_is_fine():
    assert check_year_in_lifespan(cite("See 42 F.3d 100 (1994).")).severity is Severity.OK


def test_missing_year_abstains_rather_than_passing():
    finding = check_year_in_lifespan(cite("See 42 F.3d 100."))
    assert finding.severity is Severity.UNKNOWN


def test_known_reporter_passes():
    assert check_reporter_known(cite("See 531 U.S. 98 (2000).")).severity is Severity.OK


# ------------------------------------------------- years read from the text


def test_year_is_read_positionally_not_inherited():
    """Regression: eyecite attributed a neighbour's year to a citation.

    With several citations in a row, eyecite's `year` metadata was observed
    lagging by one. Acting on that produces a false "this cannot be real"
    against a perfectly good citation - the worst error this tool can make.
    """
    text = prepare_text(
        "See Ferris v. Doyle, 42 F.2d 300 (2015), and Kaplan v. Reed, "
        "58 F.3d 900 (1985). Also Trent v. Mosby, 42 F.3d 988 (1994)."
    )
    years = [c.year for c in extract_citations(text)]
    assert years == ["2015", "1985", "1994"]


def test_year_is_none_when_there_is_no_parenthetical():
    assert cite("See 42 F.3d 100 and more.").year is None


def test_a_later_parenthetical_is_not_borrowed():
    """The window must not reach past the citation it belongs to."""
    citation = cite("See 42 F.3d 100, discussed at length in the opinion (1994).")
    assert citation.year is None


# ------------------------------------------------------- invented reporters


@pytest.mark.parametrize(
    "text,expected",
    [
        ("See 12 F.5d 40 (2001).", ["12 F.5d 40"]),
        ("See 999 Fake.Rep. 12 (2020).", ["999 Fake.Rep. 12"]),
        # Real citation shapes that are not case reporters must never fire.
        ("Under 42 U.S.C. 1983 relief is available.", []),
        ("See 29 C.F.R. 1910 for the standard.", []),
        ("See 58 Harv. L. Rev. 12 (1944).", []),
        ("See 110 Yale L.J. 1 (2000).", []),
        # Ordinary prose.
        ("The meeting is on 3 March 2020 and covers 2 of 5 items.", []),
        ("Invoice 12 Main Street 4 was paid.", []),
        ("See Bush v. Gore, 531 U.S. 98 (2000).", []),
    ],
)
def test_invented_reporter_detection(text, expected):
    cleaned = prepare_text(text)
    spans = [(c.start, c.end) for c in extract_citations(cleaned)]
    assert [f.raw for f in find_invented_reporters(cleaned, spans)] == expected


def test_real_citations_are_never_double_reported():
    cleaned = prepare_text("See 42 F.3d 100 (1994) and 12 F.5d 40 (2001).")
    spans = [(c.start, c.end) for c in extract_citations(cleaned)]
    found = find_invented_reporters(cleaned, spans)
    assert [f.raw for f in found] == ["12 F.5d 40"]


# ------------------------------------------------------ corpus-derived checks


def test_volume_year_trend_abstains_on_a_small_corpus():
    """A trend fitted on a handful of points manufactures confidence."""
    finding = check_volume_year_trend(cite("See 42 F.3d 100 (1994)."), [(1, 1993), (2, 1994)])
    assert finding.severity is Severity.UNKNOWN
    assert "too few" in finding.message


def test_volume_year_trend_flags_a_year_far_off_the_trend():
    samples = [(v, 1993 + v // 10) for v in range(1, 300, 5)]  # ~55 volumes
    finding = check_volume_year_trend(cite("See 42 F.3d 100 (2024)."), samples)
    assert finding.severity is Severity.SUSPICIOUS


def test_volume_year_trend_accepts_a_consistent_year():
    samples = [(v, 1993 + v // 10) for v in range(1, 300, 5)]
    assert check_volume_year_trend(
        cite("See 42 F.3d 100 (1997)."), samples
    ).severity is Severity.OK


def test_page_beyond_a_complete_volume_is_impossible():
    finding = check_page_bounds(cite("See 42 F.3d 9999 (1994)."), max_page=880)
    assert finding.severity is Severity.IMPOSSIBLE


def test_page_bounds_abstain_without_data():
    assert check_page_bounds(
        cite("See 42 F.3d 9999 (1994)."), max_page=None
    ).severity is Severity.UNKNOWN


# ----------------------------------------------------------------- assembly


def test_checker_needs_no_store():
    """The lifespan check must work for reporters no corpus covers."""
    report = PlausibilityChecker().check(cite("See 900 F.2d 1 (2020)."))
    assert report.is_impossible
    assert "stopped publishing" in report.reason


def test_checker_ignores_short_forms():
    citations = extract_citations(prepare_text("See 42 F.3d 100 (1994). Id. at 102."))
    short = [c for c in citations if c.kind == "IdCitation"][0]
    assert PlausibilityChecker().check(short).findings == []


def test_impossible_short_circuits_further_checks():
    report = PlausibilityChecker().check(cite("See 58 F.3d 900 (1985)."))
    assert report.is_impossible
    assert all(f.code != "volume_year_mismatch" for f in report.findings)
