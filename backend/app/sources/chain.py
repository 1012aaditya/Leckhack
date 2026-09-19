"""Ask several databases in order, cheapest first.

With both a local corpus and a CourtListener token available, the local store
should answer first: it is instant, free, and cannot be rate limited. The API
is then only consulted for citations we do not hold - which is exactly the
traffic worth spending a rate limit on, and keeps a long document from burning
through the quota mid-demo.

Resolution rules:
  - the first source to resolve a citation wins
  - if none resolve, an authoritative "no such case" beats a silent miss, so a
    real absence is still reported as one
"""

from __future__ import annotations

from ..models import ExistenceStatus, ExtractedCitation
from .base import CaseLawSource, LookupResult


class ChainedSource:
    is_authoritative = False  # decided per result

    def __init__(self, *sources: CaseLawSource) -> None:
        self._sources = [s for s in sources if s is not None]
        if not self._sources:
            raise ValueError("ChainedSource needs at least one source.")
        self.name = " → ".join(s.name for s in self._sources)

    async def lookup(self, citation: ExtractedCitation) -> LookupResult:
        best: LookupResult | None = None
        last_error: Exception | None = None

        for source in self._sources:
            try:
                result = await source.lookup(citation)
            except Exception as exc:  # a dead source must not kill the chain
                last_error = exc
                continue

            if result.status is ExistenceStatus.RESOLVED:
                return result

            if result.status is ExistenceStatus.UNCHECKED and not citation.is_lookupable:
                return result

            authoritative = result.authoritative
            if authoritative is None:
                authoritative = getattr(source, "is_authoritative", False)

            # Keep the strongest negative seen so far.
            if best is None or (authoritative and not _is_authoritative(best)):
                result.authoritative = authoritative
                best = result

        if best is not None:
            return best

        detail = f"No database could be reached ({last_error})." if last_error else \
                 "No database could be reached."
        return LookupResult(ExistenceStatus.UNCHECKED, detail=detail, authoritative=False)


def _is_authoritative(result: LookupResult) -> bool:
    return bool(result.authoritative)
