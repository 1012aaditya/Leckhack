"""Import CourtListener's citation graph.

Their bulk export ships `search_opinionscited` with the columns
(id, depth, cited_opinion_id, citing_opinion_id) - free, no API key, no rate
limit. It is what makes stage 3 possible offline: without knowing which
opinions cite which, there is no way to look for later negative treatment.

One wrinkle. CourtListener's opinion ids are not our local row ids, so the CSV
cannot be imported verbatim. We map through the `opinion_id` we recorded when a
case was stored, and skip edges whose endpoints we do not hold - which is most
of them for a small corpus, and is correct rather than a failure.
"""

from __future__ import annotations

import csv
import gzip
from dataclasses import dataclass
from pathlib import Path

from ..store import Store


@dataclass
class GraphStats:
    rows: int = 0
    imported: int = 0
    skipped_unknown_opinion: int = 0
    skipped_malformed: int = 0

    def as_dict(self) -> dict:
        return {
            "rows_read": self.rows,
            "edges_imported": self.imported,
            "skipped_endpoint_not_held": self.skipped_unknown_opinion,
            "skipped_malformed": self.skipped_malformed,
        }


def _external_id_map(store: Store) -> dict[int, int]:
    """CourtListener opinion id -> our local opinion row id."""
    rows = store._conn.execute(  # noqa: SLF001 - intentional internal read
        "SELECT id, url FROM opinions WHERE url IS NOT NULL AND url != ''"
    ).fetchall()

    mapping: dict[int, int] = {}
    for row in rows:
        # CourtListener URLs look like /opinion/118378/bush-v-gore/
        parts = [p for p in str(row["url"]).split("/") if p]
        for index, part in enumerate(parts):
            if part == "opinion" and index + 1 < len(parts) and parts[index + 1].isdigit():
                mapping[int(parts[index + 1])] = row["id"]
                break
    return mapping


def load_citation_graph(store: Store, path: Path, limit: int | None = None) -> GraphStats:
    stats = GraphStats()
    mapping = _external_id_map(store)
    if not mapping:
        return stats

    opener = gzip.open if str(path).lower().endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace", newline="") as handle:
        for row in csv.DictReader(handle):
            if limit is not None and stats.imported >= limit:
                break
            stats.rows += 1
            try:
                citing = mapping.get(int(row["citing_opinion_id"]))
                cited = mapping.get(int(row["cited_opinion_id"]))
                depth = int(row.get("depth") or 1)
            except (KeyError, TypeError, ValueError):
                stats.skipped_malformed += 1
                continue

            if citing is None or cited is None:
                stats.skipped_unknown_opinion += 1
                continue

            store.add_citation_edge(citing, cited, depth)
            stats.imported += 1

    return stats
