"""Existence checks against a loaded corpus, and the chain that orders them."""

from pathlib import Path

import pytest

from app.audit import Auditor
from app.embeddings import LocalEmbedder
from app.extract import extract_citations
from app.ingest.cap import iter_records, load_cases
from app.judge import LexicalJudge
from app.models import ExistenceStatus, Verdict
from app.sources.base import LookupResult
from app.sources.chain import ChainedSource
from app.sources.local import LocalStoreSource
from app.store import Store

SAMPLE = Path(__file__).resolve().parents[1] / "fixtures" / "cap_sample.jsonl"


@pytest.fixture
def corpus():
    store = Store(":memory:")
    embedder = LocalEmbedder()
    load_cases(store, iter_records(SAMPLE), complete_volumes=True)
    for citation in ("42 F.3d 100", "58 F.3d 900", "91 F.3d 415"):
        from app.retrieval import index_opinion

        index_opinion(store, embedder, store.get_opinion(citation).id)
    yield store, embedder
    store.close()


def cite(text):
    return extract_citations(text)[0]


@pytest.mark.asyncio
async def test_case_we_hold_resolves(corpus):
    store, _ = corpus
    result = await LocalStoreSource(store).lookup(cite("See 42 F.3d 100."))
    assert result.status is ExistenceStatus.RESOLVED
    assert result.authoritative is True
    assert result.matches[0].case_name.startswith("Alvarez")


@pytest.mark.asyncio
async def test_miss_inside_a_covered_volume_is_authoritative(corpus):
    """We hold all of F.3d vol 42, so a missing case there really is missing."""
    store, _ = corpus
    result = await LocalStoreSource(store).lookup(cite("See 42 F.3d 999."))
    assert result.status is ExistenceStatus.NOT_FOUND
    assert result.authoritative is True


@pytest.mark.asyncio
async def test_partial_volume_cannot_support_an_absence_claim():
    """A volume we hold only part of must never produce a red verdict."""
    store = Store(":memory:")
    load_cases(store, iter_records(SAMPLE))  # no completeness assertion
    result = await LocalStoreSource(store).lookup(cite("See 42 F.3d 999."))
    assert result.status is ExistenceStatus.NOT_FOUND
    assert result.authoritative is False
    assert "only part of" in result.detail
    store.close()


@pytest.mark.asyncio
async def test_miss_outside_coverage_is_not_authoritative(corpus):
    """A partial corpus cannot prove a case does not exist."""
    store, _ = corpus
    result = await LocalStoreSource(store).lookup(cite("See 900 F.2d 1."))
    assert result.status is ExistenceStatus.NOT_FOUND
    assert result.authoritative is False
    assert "not loaded" in result.detail.lower()


@pytest.mark.asyncio
async def test_pipeline_calls_only_covered_misses_fabricated(corpus):
    store, embedder = corpus
    auditor = Auditor(
        source=LocalStoreSource(store), store=store, embedder=embedder, judge=LexicalJudge()
    )
    report = await auditor.run("See 42 F.3d 999 and also 900 F.2d 1.")
    covered, uncovered = report.citations
    assert covered.verdict is Verdict.RED
    assert uncovered.verdict is Verdict.UNKNOWN


@pytest.mark.asyncio
async def test_verdict_does_not_overclaim_the_corpus_size(corpus):
    """Regression: a three-case corpus claimed 'millions of decisions'."""
    store, embedder = corpus
    auditor = Auditor(source=LocalStoreSource(store), store=store, embedder=embedder)
    report = await auditor.run("See 42 F.3d 999.")
    assert "millions" not in report.citations[0].explanation


@pytest.mark.asyncio
async def test_stage_two_runs_on_real_corpus_text(corpus):
    store, embedder = corpus
    auditor = Auditor(
        source=LocalStoreSource(store), store=store, embedder=embedder, judge=LexicalJudge()
    )
    report = await auditor.run(
        "A residential tenant cannot contract away the implied warranty of "
        "habitability, Alvarez v. Northgate, 42 F.3d 100 (1994)."
    )
    item = report.citations[0]
    assert item.support["stance"] == "supports"
    assert item.support["quote_verified"] is True
    # Real corpus text must never be labelled as demo data.
    assert not any("synthetic" in note.lower() for note in item.notes)


# ------------------------------------------------------------------- chaining


class Silent:
    name = "silent"
    is_authoritative = False

    async def lookup(self, citation):
        return LookupResult(ExistenceStatus.NOT_FOUND, detail="nothing here",
                            authoritative=False)


class Knows:
    name = "knows"
    is_authoritative = True

    async def lookup(self, citation):
        from app.models import CaseMatch

        return LookupResult(
            ExistenceStatus.RESOLVED,
            matches=[CaseMatch(case_name="Found v. It", source="knows")],
            authoritative=True,
        )


class Broken:
    name = "broken"
    is_authoritative = True

    async def lookup(self, citation):
        raise RuntimeError("database down")


@pytest.mark.asyncio
async def test_chain_returns_the_first_resolution():
    result = await ChainedSource(Silent(), Knows()).lookup(cite("See 1 U.S. 1."))
    assert result.status is ExistenceStatus.RESOLVED


@pytest.mark.asyncio
async def test_chain_survives_a_broken_source():
    """One dead database must not take the whole lookup down."""
    result = await ChainedSource(Broken(), Knows()).lookup(cite("See 1 U.S. 1."))
    assert result.status is ExistenceStatus.RESOLVED


@pytest.mark.asyncio
async def test_chain_prefers_an_authoritative_negative():
    class Definite:
        name = "definite"
        is_authoritative = True

        async def lookup(self, citation):
            return LookupResult(ExistenceStatus.NOT_FOUND, detail="definitely absent",
                                authoritative=True)

    result = await ChainedSource(Silent(), Definite()).lookup(cite("See 1 U.S. 1."))
    assert result.status is ExistenceStatus.NOT_FOUND
    assert result.authoritative is True


@pytest.mark.asyncio
async def test_chain_reports_unchecked_when_every_source_fails():
    result = await ChainedSource(Broken()).lookup(cite("See 1 U.S. 1."))
    assert result.status is ExistenceStatus.UNCHECKED
    assert not result.authoritative
