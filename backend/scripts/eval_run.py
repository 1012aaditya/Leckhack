#!/usr/bin/env python3
"""Measure the auditor against labelled cases.

This is what turns the project from a demo into a finding. Run it and you can
say what the tool actually catches, with a number, instead of asserting that it
works.

    python scripts/eval_run.py
    python scripts/eval_run.py --json results.json

Two measurements:

  Fabrication detection - does stage 1 flag invented citations and leave real
  ones alone? Recall is the number that matters: a fabricated citation the tool
  misses is the failure that reaches a court.

  Claim support - does stage 2 notice when a real case is cited for something it
  never held? Scored as a binary "did the tool accept this claim or not", since
  `contradicts`, `not_addressed` and `unclear` all correctly decline to endorse.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.audit import Auditor  # noqa: E402
from app.config import describe_components, get_embedder, get_judge, get_store  # noqa: E402
from app.models import Verdict  # noqa: E402
from app.sources.fixtures import FixtureSource  # noqa: E402

EVAL_SET = Path(__file__).resolve().parents[1] / "fixtures" / "eval_set.json"


class AuthoritativeFixtureSource(FixtureSource):
    """The offline corpus, treated as complete.

    Fabrication detection is only meaningful against a database that is allowed
    to say "no such case". The real run uses CourtListener; this makes the
    measurement runnable before access is approved.
    """

    name = "offline corpus (treated as authoritative for evaluation)"
    is_authoritative = True


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 3) if denominator else 0.0


async def run_existence(auditor: Auditor, items: list[dict]) -> dict:
    tp = fp = tn = fn = 0
    misses = []

    for item in items:
        report = await auditor.run(item["text"])
        flagged = any(c.verdict is Verdict.RED for c in report.citations)
        fabricated = item["label"] == "fabricated"

        if fabricated and flagged:
            tp += 1
        elif fabricated and not flagged:
            fn += 1
            misses.append({"text": item["text"], "error": "missed a fabricated citation"})
        elif not fabricated and flagged:
            fp += 1
            misses.append({"text": item["text"], "error": "flagged a real case as fake"})
        else:
            tn += 1

    precision = _rate(tp, tp + fp)
    recall = _rate(tp, tp + fn)
    f1 = round(2 * precision * recall / (precision + recall), 3) if precision + recall else 0.0
    return {
        "total": len(items),
        "true_positives": tp, "false_positives": fp,
        "true_negatives": tn, "false_negatives": fn,
        "precision": precision, "recall": recall, "f1": f1,
        "accuracy": _rate(tp + tn, len(items)),
        "failures": misses,
    }


async def run_stance(auditor: Auditor, items: list[dict]) -> dict:
    correct = 0
    failures = []

    for item in items:
        report = await auditor.run(item["text"])
        lookupable = [c for c in report.citations if c.citation.is_lookupable]
        support = lookupable[0].support if lookupable else None
        stance = support["stance"] if support else "unchecked"

        endorsed = stance == "supports"
        want_endorsed = item["expected"] == "supports"

        if endorsed == want_endorsed:
            correct += 1
        else:
            failures.append(
                {
                    "text": item["text"],
                    "expected": item["expected"],
                    "got": stance,
                    "note": item.get("note", ""),
                }
            )

    return {
        "total": len(items),
        "correct": correct,
        "accuracy": _rate(correct, len(items)),
        "failures": failures,
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="Write full results to this file.")
    args = parser.parse_args()

    data = json.loads(EVAL_SET.read_text())
    auditor = Auditor(
        source=AuthoritativeFixtureSource(),
        store=get_store(),
        embedder=get_embedder(),
        judge=get_judge(),
    )

    components = describe_components()
    existence = await run_existence(auditor, data["existence"])
    stance = await run_stance(auditor, data["stance"])

    offline = not components["database_authoritative"] or not components["judge_is_model_based"]

    print("\n  CITATION AUDITOR - EVALUATION")
    print(f"  {'=' * 52}")
    for key, value in components.items():
        print(f"  {key:24} {value}")

    print(f"\n  FABRICATION DETECTION  (n={existence['total']})")
    print(f"  {'-' * 52}")
    print(f"  precision {existence['precision']:>6}   of the citations we called fake, this many were")
    print(f"  recall    {existence['recall']:>6}   of the fabricated citations, this many were caught")
    print(f"  F1        {existence['f1']:>6}")
    print(f"  accuracy  {existence['accuracy']:>6}")

    print(f"\n  CLAIM SUPPORT  (n={stance['total']})")
    print(f"  {'-' * 52}")
    print(f"  accuracy  {stance['accuracy']:>6}   correctly endorsed or declined to endorse")
    if not get_judge().is_model_based:
        print("  note: measured with the offline word-matching fallback.")
        print("        Configure ANTHROPIC_API_KEY to measure the real check.")

    if offline:
        print(f"\n  {'!' * 52}")
        print("  THESE NUMBERS ARE NOT A REAL MEASUREMENT.")
        print("  Running against the offline corpus, \"fabricated\" only means")
        print("  \"absent from a small fixture file\", and the eval text was written")
        print("  alongside the corpus it is scored on. Near-perfect scores here say")
        print("  the machinery works, not that the tool does.")
        print("  Load Caselaw Access Project data and real model-generated citations")
        print("  before quoting any of this.")
        print(f"  {'!' * 52}")

    failures = existence["failures"] + stance["failures"]
    if failures:
        print(f"\n  FAILURES  ({len(failures)})")
        print(f"  {'-' * 52}")
        for failure in failures:
            print(f"  - {failure['text'][:70]}")
            detail = failure.get("error") or f"expected {failure['expected']}, got {failure['got']}"
            print(f"    {detail}")
    print()

    if args.json:
        args.json.write_text(
            json.dumps(
                {"components": components, "existence": existence, "stance": stance},
                indent=2,
            )
        )
        print(f"  Full results written to {args.json}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
