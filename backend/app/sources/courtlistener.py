"""Live existence checks against CourtListener.

Stage 1 of the audit, and deliberately the dumbest part of the system: it asks
a database whether a citation resolves and reports the answer. There is no
model anywhere in this path. Whether a case exists is a fact, not a judgement,
so nothing here is permitted to reason about it.

Free Law Project documents this endpoint as "a guardrail to help prevent
hallucinated citations", which is precisely the use we are putting it to.

API notes (see docs/data-sources.md):
  - POST /api/rest/v4/citation-lookup/
  - Auth: `Authorization: Token <token>`
  - Accepts raw text up to 64,000 characters, or volume/reporter/page
  - At most 250 citations per request
  - Throttled at 60 valid citations per minute; over-quota returns HTTP 429
    carrying a `wait_until` timestamp

RESPONSE SHAPE IS UNVERIFIED. It was written from documentation, not from a
live call, so parsing here is deliberately tolerant: unexpected keys are
ignored rather than raising. Run `scripts/probe_courtlistener.py` once a token
is available to dump a real response and tighten this up.
"""

from __future__ import annotations

import httpx

from ..models import CaseMatch, ExistenceStatus, ExtractedCitation
from .base import LookupResult

# Documented per-citation status codes, mapped onto our vocabulary.
_STATUS_MAP = {
    200: ExistenceStatus.RESOLVED,
    404: ExistenceStatus.NOT_FOUND,
    300: ExistenceStatus.AMBIGUOUS,
    400: ExistenceStatus.BAD_REPORTER,
}

MAX_TEXT_CHARS = 64_000
MAX_CITATIONS_PER_REQUEST = 250


class CourtListenerError(RuntimeError):
    """Raised when the API itself fails, as distinct from a citation not resolving."""


class RateLimited(CourtListenerError):
    def __init__(self, wait_until: str | None) -> None:
        self.wait_until = wait_until
        super().__init__(
            f"CourtListener rate limit reached; retry after {wait_until or 'a short wait'}."
        )


class CourtListenerSource:
    name = "courtlistener"
    is_authoritative = True

    def __init__(
        self,
        token: str,
        base_url: str = "https://www.courtlistener.com",
        timeout: float = 30.0,
    ) -> None:
        if not token:
            raise ValueError("CourtListener requires an API token.")
        self._endpoint = f"{base_url.rstrip('/')}/api/rest/v4/citation-lookup/"
        self._headers = {"Authorization": f"Token {token}"}
        self._timeout = timeout

    async def lookup(self, citation: ExtractedCitation) -> LookupResult:
        if not citation.is_lookupable:
            return LookupResult(
                ExistenceStatus.UNCHECKED,
                detail="Short-form reference; points at an earlier citation.",
            )

        payload = {
            "volume": citation.volume,
            "reporter": citation.reporter,
            "page": citation.page,
        }
        results = await self._post(payload)
        if not results:
            return LookupResult(
                ExistenceStatus.NOT_FOUND, detail="No result returned for this citation."
            )
        return self._to_result(results[0])

    async def _post(self, payload: dict) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                self._endpoint, headers=self._headers, json=payload
            )

        if response.status_code == 429:
            wait_until = None
            try:
                wait_until = response.json().get("wait_until")
            except Exception:
                pass
            raise RateLimited(wait_until)

        if response.status_code == 401:
            raise CourtListenerError(
                "CourtListener rejected the token. Check COURTLISTENER_TOKEN."
            )

        if response.status_code >= 400:
            raise CourtListenerError(
                f"CourtListener returned HTTP {response.status_code}: {response.text[:200]}"
            )

        body = response.json()
        # Tolerant: the endpoint is documented as returning a list, but accept a
        # wrapped object too rather than crashing a live demo over a key name.
        if isinstance(body, list):
            return body
        if isinstance(body, dict):
            for key in ("results", "citations", "data"):
                if isinstance(body.get(key), list):
                    return body[key]
            return [body]
        return []

    def _to_result(self, entry: dict) -> LookupResult:
        status = _STATUS_MAP.get(entry.get("status"), ExistenceStatus.UNCHECKED)
        matches = [
            self._to_match(cluster, entry)
            for cluster in (entry.get("clusters") or [])
            if isinstance(cluster, dict)
        ]

        # A resolved status with no cluster attached is contradictory; treat it
        # as unverified rather than quietly reporting a case we cannot show.
        if status is ExistenceStatus.RESOLVED and not matches:
            return LookupResult(
                ExistenceStatus.UNCHECKED,
                detail="API reported a match but returned no case details.",
            )

        return LookupResult(
            status, matches=matches, detail=entry.get("error_message") or ""
        )

    def _to_match(self, cluster: dict, entry: dict) -> CaseMatch:
        url = cluster.get("absolute_url")
        if url and url.startswith("/"):
            url = f"https://www.courtlistener.com{url}"
        return CaseMatch(
            case_name=cluster.get("case_name") or cluster.get("caseName"),
            citation=entry.get("citation"),
            court=cluster.get("court") or cluster.get("court_id"),
            date_filed=cluster.get("date_filed") or cluster.get("dateFiled"),
            url=url,
            opinion_id=cluster.get("id"),
            source=self.name,
        )
