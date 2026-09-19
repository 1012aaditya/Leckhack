#!/usr/bin/env python3
"""Load real Caselaw Access Project data into the local store.

CAP is CC0 and unrestricted since March 2024. Download a slice first - a
reporter volume or two is plenty, do not pull all 6.4 million cases:

    # Hugging Face (easiest)
    pip install datasets
    python -c "from datasets import load_dataset; \
        load_dataset('free-law/Caselaw_Access_Project', split='train', streaming=True)"

    # or direct bulk files
    https://case.law/download/

Then:

    python scripts/load_cap.py --inspect path/to/file.jsonl    # check the shape FIRST
    python scripts/load_cap.py path/to/file.jsonl --limit 2000
    python scripts/load_cap.py path/to/dir/ --reporter F.3d --index

`--inspect` is not optional ceremony. CAP has shipped in several shapes and the
parser here is tolerant rather than verified - inspect prints the keys it found
and what it made of the first few records, so a silent mis-parse becomes
visible before it fills your database.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_embedder, get_settings  # noqa: E402
from app.ingest.cap import iter_records, load_cases, normalize_record  # noqa: E402
from app.retrieval import index_opinion  # noqa: E402
from app.store import Store  # noqa: E402


def inspect(path: Path, count: int) -> int:
    """Print what the parser makes of the first few records, and stop."""
    print(f"\n  Inspecting {path}\n  {'=' * 64}")
    shown = 0
    for record in iter_records(path):
        if shown >= count:
            break
        shown += 1
        print(f"\n  RECORD {shown}")
        print(f"  top-level keys: {sorted(record.keys())}")

        casebody = record.get("casebody")
        if isinstance(casebody, dict):
            print(f"  casebody keys:  {sorted(casebody.keys())}")
            if isinstance(casebody.get("data"), dict):
                print(f"  casebody.data:  {sorted(casebody['data'].keys())}  (classic CAP shape)")
            elif "opinions" in casebody:
                print("  casebody.opinions present            (2024 static.case.law shape)")
        elif "text" in record:
            print("  flat `text` column present             (flattened export shape)")

        case = normalize_record(record)
        if case is None:
            print("  -> PARSED: nothing usable (no citation eyecite could read)")
            print(f"     raw citations field: {json.dumps(record.get('citations'))[:160]}")
            continue

        print(f"  -> citation:  {case.citation}   (reporter={case.reporter} volume={case.volume})")
        print(f"     name:      {case.case_name}")
        print(f"     court:     {case.court}")
        print(f"     date:      {case.date_filed}")
        print(f"     text:      {len(case.text)} chars")
        if case.text:
            print(f"     opens:     {case.text[:110]!r}")
        else:
            print("     WARNING:   no opinion text - stage 2 cannot run on this case")

    if shown == 0:
        print("\n  No records could be read from that path at all.")
        return 1
    print(f"\n  Read {shown} record(s). If the citations and text look right, drop "
          f"--inspect to import.\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("path", type=Path, help="File or directory of CAP data.")
    parser.add_argument("--inspect", action="store_true",
                        help="Show how the first records parse, then exit without importing.")
    parser.add_argument("--inspect-count", type=int, default=3)
    parser.add_argument("--limit", type=int, help="Stop after this many cases.")
    parser.add_argument("--reporter", help='Only load this reporter, e.g. "F.3d".')
    parser.add_argument("--index", action="store_true",
                        help="Build the retrieval index as cases load (slower; needed for stage 2).")
    parser.add_argument("--allow-missing-text", action="store_true",
                        help="Import cases with no opinion body. They cannot answer stage 2.")
    parser.add_argument("--complete-volumes", action="store_true",
                        help="Assert that every reporter volume in this file was loaded "
                             "in full. Only then may the auditor report a missing "
                             "citation as fabricated. CAP bulk files are organised by "
                             "volume, so this is usually right for them - but it is an "
                             "assertion you are making, not one the loader can check.")
    parser.add_argument("--synthetic", action="store_true",
                        help="Mark this corpus as invented text (use for the bundled "
                             "format sample). The app then labels it everywhere it appears.")
    args = parser.parse_args()

    if not args.path.exists():
        print(f"No such path: {args.path}", file=sys.stderr)
        return 1

    if args.inspect:
        return inspect(args.path, args.inspect_count)

    settings = get_settings()
    store = Store(Path(settings.database_path))
    embedder = get_embedder(settings) if args.index else None
    indexed = 0

    def after_case(opinion_id: int, _case) -> None:
        nonlocal indexed
        if embedder is not None:
            indexed += index_opinion(store, embedder, opinion_id)
        if (indexed or 0) and indexed % 500 == 0:
            print(f"    … {indexed} chunks indexed")

    print(f"\n  Loading from {args.path}")
    if args.synthetic:
        print("  Marked SYNTHETIC - the app will label this text as invented.")
    if embedder is not None:
        print(f"  Indexing with {embedder.name}")

    stats = load_cases(
        store,
        iter_records(args.path),
        source=("caselaw-access-project (synthetic format sample)"
                if args.synthetic else "caselaw-access-project"),
        limit=args.limit,
        reporter_filter=args.reporter,
        require_text=not args.allow_missing_text,
        is_synthetic=args.synthetic,
        complete_volumes=args.complete_volumes,
        on_case=after_case,
    )

    print(f"\n  {'=' * 60}")
    for key, value in stats.as_dict().items():
        print(f"  {key:24} {value}")
    if embedder is not None:
        print(f"  {'chunks_indexed':24} {indexed}")

    print(f"\n  Corpus now holds {store.opinion_count()} opinions.")
    print(f"  {'-' * 60}")
    print("  COVERAGE  (what the auditor may call fabricated)")
    for row in store.coverage_summary():
        print(f"    {row['reporter']:<12} {row['volumes']:>4} volume(s) "
              f"({row['complete_volumes'] or 0} complete), {row['cases']:>6} cases   "
              f"vols {row['first_volume']}–{row['last_volume']}")
    if not args.complete_volumes:
        print(
            "\n  No volume is marked complete, so a missing citation is reported as\n"
            "  unchecked rather than fabricated. Pass --complete-volumes if you\n"
            "  downloaded whole volumes and want absence treated as evidence.\n"
        )
    else:
        print(
            "\n  Volumes are marked COMPLETE: a citation missing from one is reported\n"
            "  as fabricated. Anything outside them stays unchecked.\n"
        )

    if not args.index:
        print("  Note: run again with --index, or stage 2 has no passages to search.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
