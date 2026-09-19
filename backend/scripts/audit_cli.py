#!/usr/bin/env python3
"""Audit legal text from the command line.

    python scripts/audit_cli.py "Bush v. Gore, 531 U.S. 98 (2000)."
    cat brief.txt | python scripts/audit_cli.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.audit import audit_text  # noqa: E402
from app.config import get_settings, get_source  # noqa: E402
from app.models import Verdict  # noqa: E402

LIGHTS = {
    Verdict.GREEN: "\033[92m[ OK ]\033[0m",
    Verdict.AMBER: "\033[93m[WARN]\033[0m",
    Verdict.RED: "\033[91m[FAKE]\033[0m",
    Verdict.UNKNOWN: "\033[90m[ ?  ]\033[0m",
}


async def main() -> int:
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read()
    if not text.strip():
        print("No text supplied.", file=sys.stderr)
        return 1

    settings = get_settings()
    report = await audit_text(text, get_source(settings))

    print(f"\n  {report.headline}")
    print(f"  database: {report.source_used}")
    if not settings.has_live_source:
        print("  \033[93mnote: offline sample only - cannot confirm a case is fabricated\033[0m")
    print()

    for item in report.citations:
        print(f"  {LIGHTS[item.verdict]} {item.citation.raw}")
        print(f"         {item.explanation}")
        for match in item.matches:
            if match.url:
                print(f"         {match.url}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
