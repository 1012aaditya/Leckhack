"""The contract every case law database must satisfy.

Two implementations exist: `FixtureSource` (offline, for development and for a
demo that must survive dead venue wifi) and `CourtListenerSource` (live).
Swapping between them changes no code outside this package.
"""

from __future__ import annotations

from typing import Protocol

from ..models import CaseMatch, ExistenceStatus, ExtractedCitation


class LookupResult:
    """What a database says about one citation."""

    def __init__(
        self,
        status: ExistenceStatus,
        matches: list[CaseMatch] | None = None,
        detail: str = "",
        authoritative: bool | None = None,
    ) -> None:
        self.status = status
        self.matches = matches or []
        self.detail = detail
        self.authoritative = authoritative
        """Whether THIS answer may be reported as "no such case".

        Per result rather than per source, because a partial corpus can be
        authoritative about one citation and silent about another: loading
        F.3d volume 42 licenses "42 F.3d 999 does not exist", but says nothing
        at all about 900 F.2d 1. None means fall back to the source default."""

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"LookupResult({self.status.value}, {len(self.matches)} matches)"


class CaseLawSource(Protocol):
    """A database that can say whether a citation resolves to a real case."""

    name: str
    is_authoritative: bool
    """False for stand-ins whose 'not found' must not be read as 'fake'."""

    async def lookup(self, citation: ExtractedCitation) -> LookupResult: ...
