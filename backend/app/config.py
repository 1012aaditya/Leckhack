"""Runtime configuration and source selection."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from .sources.base import CaseLawSource
from .sources.courtlistener import CourtListenerSource
from .sources.fixtures import FixtureSource


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    courtlistener_token: str = ""
    courtlistener_base_url: str = "https://www.courtlistener.com"

    @property
    def has_live_source(self) -> bool:
        return bool(self.courtlistener_token.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_source(settings: Settings | None = None) -> CaseLawSource:
    """Pick the best available database.

    Live CourtListener when a token is configured, the offline fixture sample
    otherwise. Nothing outside this function needs to know which is in use -
    but the audit layer does check `is_authoritative` before it is willing to
    call a citation fabricated.
    """
    settings = settings or get_settings()
    if settings.has_live_source:
        return CourtListenerSource(
            token=settings.courtlistener_token,
            base_url=settings.courtlistener_base_url,
        )
    return FixtureSource()
