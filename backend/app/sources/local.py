"""Existence checks against the case law we have actually loaded.

Once real Caselaw Access Project data is in the store, this is the primary
source: it is fast, needs no network, and cannot be rate limited - which is
what makes a demo safe.

The interesting part is when it is allowed to say a case does not exist. A
partial corpus cannot prove absence in general, but it can prove it locally: if
we hold every case in F.3d volume 42, then "42 F.3d 999" genuinely does not
exist, while "900 F.2d 1" is simply outside what we loaded. The store's
coverage table records which reporter volumes are complete, and this source
answers accordingly rather than treating every miss the same way.
"""

from __future__ import annotations

from ..models import CaseMatch, ExistenceStatus, ExtractedCitation
from ..store import Store
from .base import LookupResult


class LocalStoreSource:
    name = "local corpus"

    # Authority is decided per citation from coverage, so the source-level flag
    # stays False: nothing is authoritative by default.
    is_authoritative = False

    def __init__(self, store: Store, label: str | None = None) -> None:
        self._store = store
        if label:
            self.name = label

    async def lookup(self, citation: ExtractedCitation) -> LookupResult:
        if not citation.is_lookupable:
            return LookupResult(
                ExistenceStatus.UNCHECKED,
                detail="Short-form reference; points at an earlier citation.",
            )

        key = f"{citation.volume} {citation.reporter} {citation.page}"
        opinion = self._store.get_opinion(key)

        if opinion is not None:
            return LookupResult(
                ExistenceStatus.RESOLVED,
                matches=[
                    CaseMatch(
                        case_name=opinion.case_name,
                        citation=opinion.citation,
                        court=opinion.court,
                        date_filed=opinion.date_filed,
                        url=opinion.url,
                        opinion_id=opinion.id,
                        source=opinion.source,
                    )
                ],
                authoritative=True,
            )

        reporter, volume = str(citation.reporter), str(citation.volume)

        if self._store.covers(reporter, volume):
            return LookupResult(
                ExistenceStatus.NOT_FOUND,
                detail=(
                    f"We hold every case in {reporter} volume {volume}, "
                    f"and this is not among them."
                ),
                authoritative=True,
            )

        # Holding part of a volume proves nothing about the rest of it. Saying
        # so is less satisfying than a red verdict and is the only defensible
        # answer.
        if self._store.has_volume(reporter, volume):
            return LookupResult(
                ExistenceStatus.NOT_FOUND,
                detail=(
                    f"We hold only part of {reporter} volume {volume}, so we cannot "
                    f"tell whether this case exists."
                ),
                authoritative=False,
            )

        return LookupResult(
            ExistenceStatus.NOT_FOUND,
            detail=(
                f"We have not loaded {reporter} volume {volume}, "
                f"so this citation could not be checked either way."
            ),
            authoritative=False,
        )
