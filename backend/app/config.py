"""Runtime configuration and component selection.

One rule governs this module: every component has a working default that needs
no credentials. Adding a key upgrades a component in place; it never turns the
application on. That is what makes the demo safe.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from .audit import Auditor
from .demo_data import load_demo_corpus
from .embeddings import Embedder, LocalEmbedder, VoyageEmbedder
from .judge import ClaudeJudge, Judge, LexicalJudge
from .sources.base import CaseLawSource
from .sources.chain import ChainedSource
from .sources.courtlistener import CourtListenerSource
from .sources.fixtures import FixtureSource
from .sources.local import LocalStoreSource
from .store import DEFAULT_DB, Store


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    courtlistener_token: str = ""
    courtlistener_base_url: str = "https://www.courtlistener.com"
    anthropic_api_key: str = ""
    voyage_api_key: str = ""
    database_path: str = str(DEFAULT_DB)
    load_demo_corpus_on_start: bool = True

    @property
    def has_live_source(self) -> bool:
        return bool(self.courtlistener_token.strip())

    @property
    def has_model_judge(self) -> bool:
        return bool(self.anthropic_api_key.strip())

    @property
    def has_semantic_embeddings(self) -> bool:
        return bool(self.voyage_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_source(settings: Settings | None = None) -> CaseLawSource:
    """Assemble the best chain of databases available.

    Local corpus first where one is loaded: instant, free, and it spares the
    API rate limit for the citations we genuinely do not hold. CourtListener
    after it, covering everything outside our slice and everything decided
    after CAP's 2020 cutoff. The fixture sample only when there is nothing else.
    """
    settings = settings or get_settings()
    sources: list[CaseLawSource] = []

    store = get_store()
    if store.coverage_summary():
        sources.append(LocalStoreSource(store, label="local CAP corpus"))

    if settings.has_live_source:
        sources.append(
            CourtListenerSource(
                token=settings.courtlistener_token,
                base_url=settings.courtlistener_base_url,
            )
        )

    if not sources:
        return FixtureSource()
    if len(sources) == 1:
        return sources[0]
    return ChainedSource(*sources)


def get_embedder(settings: Settings | None = None) -> Embedder:
    settings = settings or get_settings()
    if settings.has_semantic_embeddings:
        return VoyageEmbedder(api_key=settings.voyage_api_key)
    return LocalEmbedder()


def get_judge(settings: Settings | None = None) -> Judge:
    settings = settings or get_settings()
    if settings.has_model_judge:
        return ClaudeJudge(api_key=settings.anthropic_api_key)
    return LexicalJudge()


# Cached with no arguments: Settings is a pydantic model and therefore not
# hashable, and the store is process-wide state rather than per-call anyway.
@lru_cache(maxsize=1)
def get_store() -> Store:
    settings = get_settings()
    store = Store(Path(settings.database_path))
    # Skip the synthetic demo corpus once real case law is loaded - nobody
    # wants invented opinions sitting beside genuine ones.
    if settings.load_demo_corpus_on_start and not store.coverage_summary():
        # Idempotent: upserts by citation, so restarting does not duplicate.
        load_demo_corpus(store, get_embedder(settings))
    return store


def get_auditor(settings: Settings | None = None) -> Auditor:
    settings = settings or get_settings()
    return Auditor(
        source=get_source(settings),
        store=get_store(),
        embedder=get_embedder(settings),
        judge=get_judge(settings),
    )


def describe_components(settings: Settings | None = None) -> dict:
    """What is actually running, so the UI can be honest about its own limits."""
    settings = settings or get_settings()
    store = get_store()
    coverage = store.coverage_summary()
    return {
        "database": get_source(settings).name,
        "database_authoritative": (
            getattr(get_source(settings), "is_authoritative", False)
            or bool(coverage)
            or settings.has_live_source
        ),
        "corpus_opinions": store.opinion_count(),
        "corpus_coverage": coverage,
        "judge": get_judge(settings).name,
        "judge_is_model_based": get_judge(settings).is_model_based,
        "embeddings": get_embedder(settings).name,
        "embeddings_semantic": getattr(get_embedder(settings), "is_semantic", False),
    }
