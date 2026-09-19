"""Shared test fixtures.

The test environment is configured BEFORE any app module is imported, because
config caches both the settings and the store on first use. Without this the
API tests read whatever database happens to be on the developer's disk - so
loading a real corpus locally breaks the suite, which is a defect in the test
setup rather than in the code under test.
"""

import os
import tempfile
from pathlib import Path

_TEST_DB = Path(tempfile.mkdtemp(prefix="citation-auditor-tests-")) / "test.db"
os.environ["DATABASE_PATH"] = str(_TEST_DB)
os.environ["LOAD_DEMO_CORPUS_ON_START"] = "true"
for _key in ("COURTLISTENER_TOKEN", "ANTHROPIC_API_KEY", "VOYAGE_API_KEY"):
    os.environ[_key] = ""

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
