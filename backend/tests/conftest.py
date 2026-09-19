import pytest

from app.demo_data import load_demo_corpus
from app.embeddings import LocalEmbedder
from app.judge import LexicalJudge
from app.sources.fixtures import FixtureSource
from app.store import Store


class AuthoritativeSource(FixtureSource):
    """The offline corpus treated as complete, standing in for the live database."""

    name = "test (authoritative)"
    is_authoritative = True


@pytest.fixture
def embedder():
    return LocalEmbedder()


@pytest.fixture
def store(embedder):
    store = Store(":memory:")
    load_demo_corpus(store, embedder)
    yield store
    store.close()


@pytest.fixture
def auditor(store, embedder):
    from app.audit import Auditor

    return Auditor(
        source=AuthoritativeSource(), store=store, embedder=embedder, judge=LexicalJudge()
    )
