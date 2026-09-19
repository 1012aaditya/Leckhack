#!/usr/bin/env python3
"""Dump a raw CourtListener citation-lookup response.

Run this the moment API access is approved. It prints exactly what the endpoint
returns for one real and one fabricated citation, so the parsing assumptions in
app/sources/courtlistener.py can be confirmed or corrected against reality
rather than against documentation.

    export COURTLISTENER_TOKEN=...
    python scripts/probe_courtlistener.py
"""

import asyncio
import json
import os
import sys

import httpx

ENDPOINT = "https://www.courtlistener.com/api/rest/v4/citation-lookup/"

PROBES = [
    ("REAL case (expect status 200)", {"volume": "531", "reporter": "U.S.", "page": "98"}),
    ("FAKE case (expect status 404)", {"volume": "999", "reporter": "U.S.", "page": "1234"}),
    ("BAD reporter (expect status 400)", {"volume": "1", "reporter": "Fake.Rep.", "page": "1"}),
    (
        "FREE TEXT (mixed real and fake)",
        {"text": "See Bush v. Gore, 531 U.S. 98 (2000); Smith v. Nowhere, 999 U.S. 1234 (2022)."},
    ),
]


async def main() -> int:
    token = os.environ.get("COURTLISTENER_TOKEN")
    if not token:
        print("COURTLISTENER_TOKEN is not set.", file=sys.stderr)
        return 1

    headers = {"Authorization": f"Token {token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        for label, payload in PROBES:
            print(f"\n{'=' * 70}\n{label}\npayload: {payload}\n{'-' * 70}")
            try:
                response = await client.post(ENDPOINT, headers=headers, json=payload)
            except Exception as exc:
                print(f"request failed: {exc}")
                continue
            print(f"HTTP {response.status_code}")
            try:
                print(json.dumps(response.json(), indent=2)[:3000])
            except Exception:
                print(response.text[:1000])
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
