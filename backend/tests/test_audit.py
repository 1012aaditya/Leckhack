import pytest

from app.audit import audit_text
from app.models import ExistenceStatus, Verdict
from app.sources.base import LookupResult
from app.sources.courtlistener import CourtListenerError
from app.sources.fixtures import FixtureSource

MIXED = (
    "The court in Bush v. Gore, 531 U.S. 98 (2000), held otherwise. "
    "See also Smith v. Nowhere, 999 U.S. 1234 (2022). Id. at 4."
)


class AuthoritativeFixtureSource(FixtureSource):
    """Fixture data, but claiming authority - stands in for the live database."""

    name = "test (authoritative)"
    is_authoritative = True


class BrokenSource:
    name = "broken"
    is_authoritative = True

    async def lookup(self, citation):
        raise CourtListenerError("service unavailable")


@pytest.mark.asyncio
async def test_real_case_goes_green():
    report = await audit_text("Bush v. Gore, 531 U.S. 98 (2000).", FixtureSource())
    assert report.citations[0].verdict is Verdict.GREEN
    assert report.citations[0].matches[0].case_name == "Bush v. Gore"


@pytest.mark.asyncio
async def test_authoritative_source_calls_fabrication_red():
    report = await audit_text(
        "Smith v. Nowhere, 999 U.S. 1234 (2022).", AuthoritativeFixtureSource()
    )
    assert report.citations[0].verdict is Verdict.RED
    assert report.citations[0].existence is ExistenceStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_offline_source_never_claims_a_case_is_fake():
    """The integrity guarantee.

    A six-case sample missing a citation means nothing. Reporting that as RED
    would be the auditor doing exactly what it exists to catch.
    """
    report = await audit_text("Smith v. Nowhere, 999 U.S. 1234 (2022).", FixtureSource())
    assert report.citations[0].verdict is Verdict.UNKNOWN
    assert "offline sample" in report.citations[0].explanation


@pytest.mark.asyncio
async def test_database_outage_is_not_reported_as_fabrication():
    report = await audit_text("Bush v. Gore, 531 U.S. 98 (2000).", BrokenSource())
    assert report.citations[0].verdict is Verdict.UNKNOWN
    assert "Could not check" in report.citations[0].explanation


@pytest.mark.asyncio
async def test_headline_counts_only_real_problems():
    report = await audit_text(MIXED, AuthoritativeFixtureSource())
    assert report.total == 3  # two full citations plus the Id. reference
    assert report.problems == 1
    assert report.headline == "1 of 3 citations have problems."


@pytest.mark.asyncio
async def test_short_form_is_reported_not_judged():
    report = await audit_text(MIXED, AuthoritativeFixtureSource())
    short = [r for r in report.citations if r.citation.kind == "IdCitation"]
    assert short and short[0].verdict is Verdict.UNKNOWN


@pytest.mark.asyncio
async def test_text_with_no_citations():
    report = await audit_text("There is no law here at all.", FixtureSource())
    assert report.total == 0
    assert report.headline == "No case citations found in this text."


@pytest.mark.asyncio
async def test_headline_does_not_claim_unchecked_citations_passed():
    """Regression: 'All 4 citations checked out' while two were never checked."""
    report = await audit_text(
        "Bush v. Gore, 531 U.S. 98 (2000). Smith v. Nowhere, 999 U.S. 1234 (2022). Id. at 4.",
        FixtureSource(),
    )
    assert report.unchecked == 2
    assert report.headline == "1 of 3 citations checked out; 2 could not be checked."


@pytest.mark.asyncio
async def test_headline_when_nothing_could_be_checked():
    report = await audit_text("Smith v. Nowhere, 999 U.S. 1234 (2022).", FixtureSource())
    assert report.headline == "This citation could not be checked."
