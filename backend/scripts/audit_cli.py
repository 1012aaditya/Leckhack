#!/usr/bin/env python3
"""Audit legal text from the command line.

    python scripts/audit_cli.py "Bush v. Gore, 531 U.S. 98 (2000)."
    cat brief.txt | python scripts/audit_cli.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import describe_components, get_auditor, get_settings  # noqa: E402
from app.models import Verdict  # noqa: E402

DIM, RESET = "\033[90m", "\033[0m"
LIGHTS = {
    Verdict.GREEN: "\033[92m[ OK ]\033[0m",
    Verdict.AMBER: "\033[93m[WARN]\033[0m",
    Verdict.RED: "\033[91m[FAKE]\033[0m",
    Verdict.UNKNOWN: f"{DIM}[ ?  ]{RESET}",
}


def wrap(text: str, indent: str = " " * 9, width: int = 78) -> str:
    import textwrap

    return "\n".join(textwrap.wrap(text, width=width, initial_indent=indent,
                                   subsequent_indent=indent))


async def main() -> int:
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read()
    if not text.strip():
        print("No text supplied.", file=sys.stderr)
        return 1

    settings = get_settings()
    report = await get_auditor(settings).run(text)
    components = describe_components(settings)

    print(f"\n  {report.headline}")
    print(f"{DIM}  database: {components['database']}   "
          f"support check: {components['judge']}{RESET}")
    if not components["database_authoritative"]:
        print("\033[93m  note: offline sample only - cannot confirm a case is "
              "fabricated\033[0m")
    print()

    for item in report.citations:
        print(f"  {LIGHTS[item.verdict]} {item.citation.raw}")
        print(wrap(item.explanation))

        support = item.support or {}
        if support.get("quote") and support.get("quote_verified"):
            print(wrap(f'"{support["quote"]}"'))
            print(f"{DIM}         ^ confirmed word-for-word in the source opinion{RESET}")

        for match in item.matches:
            if match.url:
                print(f"{DIM}         {match.url}{RESET}")

        good_law = item.good_law or {}
        if good_law.get("checked") and good_law.get("summary"):
            print(f"{DIM}{wrap(good_law['summary'])}{RESET}")

        for note in item.notes:
            print(f"{DIM}{wrap('note: ' + note)}{RESET}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
