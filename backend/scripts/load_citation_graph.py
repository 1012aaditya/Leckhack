#!/usr/bin/env python3
"""Import CourtListener's citation-graph bulk CSV (powers stage 3).

Free, no API key, no rate limit: https://www.courtlistener.com/help/api/bulk-data/
Download `search_opinionscited`, then:

    python scripts/load_citation_graph.py opinions-cited.csv.gz

Edges are kept only where both endpoints are cases we already hold, so load
your case law first.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.ingest.citation_graph import load_citation_graph  # noqa: E402
from app.store import Store  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    if not args.path.exists():
        print(f"No such file: {args.path}", file=sys.stderr)
        return 1

    store = Store(Path(get_settings().database_path))
    stats = load_citation_graph(store, args.path, limit=args.limit)

    print()
    for key, value in stats.as_dict().items():
        print(f"  {key:28} {value}")

    if stats.imported == 0:
        print(
            "\n  No edges imported. Both endpoints of an edge must be cases already in\n"
            "  the store, matched by their CourtListener opinion id in the stored URL.\n"
            "  Load case law first, or this file covers different opinions.\n"
        )
    else:
        print("\n  Stage 3 can now look for later negative treatment.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
