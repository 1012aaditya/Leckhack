"""Offline stand-in for a real case law database.

Two jobs. It lets the whole pipeline run before API access is approved, and it
guarantees the demo works even if the venue wifi does not.

One caveat matters enough to be enforced in the type: this source is NOT
authoritative. A citation missing from the fixture file returns NOT_FOUND, but
that only means "not in our small sample" - it is not evidence of fabrication.
Callers must check `is_authoritative` before telling a user a case is fake.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..models import CaseMatch, ExistenceStatus, ExtractedCitation
from .base import LookupResult

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "cases.json"


class FixtureSource:
    name = "fixtures (offline sample)"
    is_authoritative = False

    def __init__(self, path: Path | None = None) -> None:
        raw = json.loads((path or _FIXTURE_PATH).read_text())
        self._cases = {k: v for k, v in raw.items() if not k.startswith("_")}

    async def lookup(self, citation: ExtractedCitation) -> LookupResult:
        if not citation.is_lookupable:
            return LookupResult(
                ExistenceStatus.UNCHECKED,
                detail="Short-form reference; points at an earlier citation.",
            )

        key = f"{citation.volume} {citation.reporter} {citation.page}"
        case = self._cases.get(key)

        if case is None:
            return LookupResult(
                ExistenceStatus.NOT_FOUND,
                detail=f"'{key}' is not in the offline sample.",
            )

        return LookupResult(
            ExistenceStatus.RESOLVED,
            matches=[CaseMatch(citation=key, source=self.name, **case)],
        )
