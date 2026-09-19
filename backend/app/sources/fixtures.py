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

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
_FIXTURE_PATH = _FIXTURES / "cases.json"


class FixtureSource:
    name = "fixtures (offline sample)"
    is_authoritative = False

    def __init__(self, path: Path | None = None) -> None:
        raw = json.loads((path or _FIXTURE_PATH).read_text())
        self._cases = {k: v for k, v in raw.items() if not k.startswith("_")}

        # The synthetic demo opinions are part of the offline sample too -
        # otherwise stages 2 and 3 have text to reason about for cases stage 1
        # has just declared nonexistent.
        opinions_path = (path.parent if path else _FIXTURES) / "opinions.json"
        if opinions_path.exists():
            for record in json.loads(opinions_path.read_text()).get("opinions", []):
                self._cases.setdefault(
                    record["citation"],
                    {
                        "case_name": record.get("case_name"),
                        "court": record.get("court"),
                        "date_filed": record.get("date_filed"),
                        "url": record.get("url"),
                    },
                )

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

        fields = ("case_name", "court", "date_filed", "url", "opinion_id")
        return LookupResult(
            ExistenceStatus.RESOLVED,
            matches=[
                CaseMatch(
                    citation=key,
                    source=self.name,
                    **{f: case[f] for f in fields if f in case},
                )
            ],
        )
