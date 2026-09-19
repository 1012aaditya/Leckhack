"""Load the demo corpus into the local store.

The opinion bodies here are synthetic - written for this project, not real
court text. Every record is marked `is_synthetic` and the app labels it
wherever it appears. Loading real Caselaw Access Project data replaces this
corpus; see docs/data-sources.md.
"""

from __future__ import annotations

import json
from pathlib import Path

from .embeddings import Embedder
from .retrieval import index_opinion
from .store import Store

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def load_demo_corpus(store: Store, embedder: Embedder | None = None) -> dict:
    """Load real-case metadata and the synthetic opinion corpus.

    Returns counts so a caller can report what happened rather than guess.
    """
    counts = {"cases": 0, "opinions": 0, "edges": 0, "chunks": 0}

    # cases.json carries CourtListener's own opinion_id for linking; it is not a
    # column here, so take only the fields the store knows about.
    _CASE_FIELDS = ("case_name", "court", "date_filed", "url")

    cases = json.loads((_FIXTURES / "cases.json").read_text())
    for citation, case in cases.items():
        if citation.startswith("_"):
            continue
        store.upsert_opinion(
            citation=citation,
            source="fixtures:cases",
            is_synthetic=False,
            **{k: case[k] for k in _CASE_FIELDS if k in case},
        )
        counts["cases"] += 1

    payload = json.loads((_FIXTURES / "opinions.json").read_text())
    ids: dict[str, int] = {}
    for record in payload["opinions"]:
        opinion_id = store.upsert_opinion(
            citation=record["citation"],
            text=record["text"],
            case_name=record.get("case_name"),
            court=record.get("court"),
            date_filed=record.get("date_filed"),
            url=record.get("url"),
            is_synthetic=record.get("is_synthetic", True),
            source="fixtures:opinions(synthetic)",
        )
        ids[record["citation"]] = opinion_id
        counts["opinions"] += 1
        if embedder is not None:
            counts["chunks"] += index_opinion(store, embedder, opinion_id)

    for edge in payload.get("cites", []):
        citing, cited = ids.get(edge["citing"]), ids.get(edge["cited"])
        if citing and cited:
            store.add_citation_edge(citing, cited)
            counts["edges"] += 1

    return counts
