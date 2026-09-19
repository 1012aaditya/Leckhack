"""End-to-end behaviour of the three-stage pipeline."""

import pytest

from app.audit import Auditor
from app.models import Verdict
from app.sources.fixtures import FixtureSource


@pytest.mark.asyncio
async def test_faithful_citation_passes(auditor):
    report = await auditor.run(
        "A landlord may not resort to self-help eviction, "
        "Whitfield v. Cedar Ridge Apartments, 58 F.3d 900 (1995)."
    )
    item = report.citations[0]
    assert item.verdict is Verdict.GREEN
    assert item.support["stance"] == "supports"


@pytest.mark.asyncio
async def test_real_case_cited_for_an_unrelated_claim_is_flagged(auditor):
    report = await auditor.run(
        "The court held that federal income tax deductions require substantiation, "
        "Alvarez v. Northgate Property Management, 42 F.3d 100 (1994)."
    )
    item = report.citations[0]
    assert item.verdict is Verdict.AMBER
    assert item.support["stance"] != "supports"


@pytest.mark.asyncio
async def test_fabricated_citation_is_red(auditor):
    report = await auditor.run("See Smith v. Nowhere, 999 U.S. 1234 (2022).")
    assert report.citations[0].verdict is Verdict.RED


@pytest.mark.asyncio
async def test_overruled_case_is_flagged_even_when_the_claim_is_faithful(auditor):
    report = await auditor.run(
        "A residential tenant cannot contract away the implied warranty of "
        "habitability, Alvarez v. Northgate Property Management, 42 F.3d 100 (1994)."
    )
    item = report.citations[0]
    assert item.verdict is Verdict.AMBER
    assert item.good_law["findings"][0]["treatment"] == "overruled"


@pytest.mark.asyncio
async def test_stage_one_alone_still_works(store):
    """Without a store, embedder or judge the tool degrades to existence checks.

    That is still a working product - it catches outright fabrication - and it
    must not crash or silently claim the later checks ran.
    """
    class Authoritative(FixtureSource):
        name = "stage-one-only"
        is_authoritative = True

    report = await Auditor(source=Authoritative()).run(
        "See Bush v. Gore, 531 U.S. 98 (2000). See Smith v. Nowhere, 999 U.S. 1234 (2022)."
    )
    assert report.citations[0].verdict is Verdict.GREEN
    assert report.citations[0].support is None
    assert "could not check whether it says" in report.citations[0].explanation.lower()
    assert report.citations[1].verdict is Verdict.RED


@pytest.mark.asyncio
async def test_short_forms_carry_no_claim(auditor):
    """A short-form reference is never checked, so it must not display a claim."""
    report = await auditor.run(
        "A landlord may not use self-help, Whitfield v. Cedar Ridge, 58 F.3d 900 (1995). "
        "Id. at 902."
    )
    short = [c for c in report.citations if c.citation.kind == "IdCitation"]
    assert short and short[0].claim == ""
