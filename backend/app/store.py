"""Local store for opinion text, the retrieval index, and the citation graph.

SQLite, deliberately. It needs no server, starts instantly, and travels in a
single file - which matters because the demo has to survive a venue with no
working wifi. The schema mirrors Postgres closely enough that moving over is a
migration rather than a rewrite (see app/schema.sql).
"""

from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np

_SCHEMA = Path(__file__).with_name("schema.sql")
DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "auditor.db"


@dataclass(frozen=True)
class StoredOpinion:
    id: int
    citation: str
    case_name: str | None
    court: str | None
    date_filed: str | None
    url: str | None
    text: str
    is_synthetic: bool
    source: str


@dataclass(frozen=True)
class StoredChunk:
    id: int
    opinion_id: int
    ordinal: int
    text: str


class Store:
    def __init__(self, path: Path | str = DEFAULT_DB) -> None:
        self.path = Path(path)
        if self.path != Path(":memory:"):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA.read_text())
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ---------------------------------------------------------------- opinions

    def upsert_opinion(
        self,
        citation: str,
        text: str = "",
        case_name: str | None = None,
        court: str | None = None,
        date_filed: str | None = None,
        url: str | None = None,
        is_synthetic: bool = False,
        source: str = "unknown",
    ) -> int:
        cursor = self._conn.execute(
            """
            INSERT INTO opinions (citation, case_name, court, date_filed, url, text,
                                  is_synthetic, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(citation) DO UPDATE SET
                case_name  = COALESCE(excluded.case_name, opinions.case_name),
                court      = COALESCE(excluded.court, opinions.court),
                date_filed = COALESCE(excluded.date_filed, opinions.date_filed),
                url        = COALESCE(excluded.url, opinions.url),
                -- never let an empty fetch wipe text we already hold
                text       = CASE WHEN excluded.text != '' THEN excluded.text
                                  ELSE opinions.text END,
                is_synthetic = excluded.is_synthetic,
                source     = excluded.source
            RETURNING id
            """,
            (citation, case_name, court, date_filed, url, text,
             int(is_synthetic), source),
        )
        opinion_id = cursor.fetchone()[0]
        self._conn.commit()
        return opinion_id

    def get_opinion(self, citation: str) -> StoredOpinion | None:
        row = self._conn.execute(
            "SELECT * FROM opinions WHERE citation = ?", (citation,)
        ).fetchone()
        return self._to_opinion(row) if row else None

    def get_opinion_by_id(self, opinion_id: int) -> StoredOpinion | None:
        row = self._conn.execute(
            "SELECT * FROM opinions WHERE id = ?", (opinion_id,)
        ).fetchone()
        return self._to_opinion(row) if row else None

    @staticmethod
    def _to_opinion(row: sqlite3.Row) -> StoredOpinion:
        return StoredOpinion(
            id=row["id"],
            citation=row["citation"],
            case_name=row["case_name"],
            court=row["court"],
            date_filed=row["date_filed"],
            url=row["url"],
            text=row["text"],
            is_synthetic=bool(row["is_synthetic"]),
            source=row["source"],
        )

    # ------------------------------------------------------------------ chunks

    def replace_chunks(self, opinion_id: int, texts: list[str]) -> list[int]:
        self._conn.execute("DELETE FROM chunks WHERE opinion_id = ?", (opinion_id,))
        ids = []
        for ordinal, text in enumerate(texts):
            cursor = self._conn.execute(
                "INSERT INTO chunks (opinion_id, ordinal, text) VALUES (?, ?, ?) RETURNING id",
                (opinion_id, ordinal, text),
            )
            ids.append(cursor.fetchone()[0])
        self._conn.commit()
        return ids

    def chunks_for(self, opinion_id: int) -> list[StoredChunk]:
        rows = self._conn.execute(
            "SELECT * FROM chunks WHERE opinion_id = ? ORDER BY ordinal", (opinion_id,)
        ).fetchall()
        return [
            StoredChunk(id=r["id"], opinion_id=r["opinion_id"], ordinal=r["ordinal"],
                        text=r["text"])
            for r in rows
        ]

    # -------------------------------------------------------------- embeddings

    def save_embeddings(
        self, chunk_ids: list[int], vectors: np.ndarray, model: str
    ) -> None:
        vectors = np.asarray(vectors, dtype=np.float32)
        if vectors.shape[0] != len(chunk_ids):
            raise ValueError("Vector count does not match chunk count.")
        self._conn.executemany(
            "INSERT OR REPLACE INTO embeddings (chunk_id, model, dim, vector) VALUES (?, ?, ?, ?)",
            [
                (cid, model, int(vectors.shape[1]), vectors[i].tobytes())
                for i, cid in enumerate(chunk_ids)
            ],
        )
        self._conn.commit()

    def load_embeddings(self, opinion_id: int) -> tuple[list[StoredChunk], np.ndarray]:
        """Return an opinion's chunks alongside their vectors, aligned by index."""
        rows = self._conn.execute(
            """
            SELECT c.id, c.opinion_id, c.ordinal, c.text, e.vector, e.dim
            FROM chunks c JOIN embeddings e ON e.chunk_id = c.id
            WHERE c.opinion_id = ? ORDER BY c.ordinal
            """,
            (opinion_id,),
        ).fetchall()
        if not rows:
            return [], np.zeros((0, 0), dtype=np.float32)

        chunks = [
            StoredChunk(id=r["id"], opinion_id=r["opinion_id"], ordinal=r["ordinal"],
                        text=r["text"])
            for r in rows
        ]
        matrix = np.vstack(
            [np.frombuffer(r["vector"], dtype=np.float32).reshape(1, r["dim"]) for r in rows]
        )
        return chunks, matrix

    # ---------------------------------------------------------- citation graph

    def add_citation_edge(self, citing_id: int, cited_id: int, depth: int = 1) -> None:
        self._conn.execute(
            """INSERT INTO cites (citing_opinion_id, cited_opinion_id, depth)
               VALUES (?, ?, ?)
               ON CONFLICT(citing_opinion_id, cited_opinion_id) DO UPDATE SET depth = excluded.depth""",
            (citing_id, cited_id, depth),
        )
        self._conn.commit()

    def citing_opinions(self, cited_id: int) -> list[StoredOpinion]:
        """Every opinion that cites this one, newest first.

        Newest first because later treatment is what determines whether a case
        is still good law.
        """
        rows = self._conn.execute(
            """
            SELECT o.* FROM cites c JOIN opinions o ON o.id = c.citing_opinion_id
            WHERE c.cited_opinion_id = ?
            ORDER BY COALESCE(o.date_filed, '') DESC
            """,
            (cited_id,),
        ).fetchall()
        return [self._to_opinion(r) for r in rows]

    # ---------------------------------------------------------- corpus coverage

    def record_coverage(
        self, reporter: str, volume: str, source: str, case_count: int
    ) -> None:
        """Note that we hold a complete reporter volume."""
        self._conn.execute(
            """INSERT INTO corpus_coverage (reporter, volume, source, case_count)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(reporter, volume) DO UPDATE SET
                   source = excluded.source,
                   case_count = excluded.case_count,
                   loaded_at = datetime('now')""",
            (reporter, volume, source, case_count),
        )
        self._conn.commit()

    def covers(self, reporter: str, volume: str) -> bool:
        """Whether a miss for this citation may be reported as 'no such case'."""
        row = self._conn.execute(
            "SELECT 1 FROM corpus_coverage WHERE reporter = ? AND volume = ?",
            (reporter, volume),
        ).fetchone()
        return row is not None

    def coverage_summary(self) -> list[dict]:
        rows = self._conn.execute(
            """SELECT reporter, COUNT(*) AS volumes, SUM(case_count) AS cases,
                      MIN(volume) AS first_volume, MAX(volume) AS last_volume,
                      MIN(source) AS source
               FROM corpus_coverage GROUP BY reporter ORDER BY reporter"""
        ).fetchall()
        return [dict(r) for r in rows]

    def opinion_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM opinions").fetchone()[0]

    def has_synthetic_corpus(self) -> bool:
        """Whether any loaded opinion body is invented rather than a real record.

        Surfaced in the UI: a corpus can be structurally real and still hold
        fictional text, and a viewer must not have to guess which.
        """
        row = self._conn.execute(
            "SELECT 1 FROM opinions WHERE is_synthetic = 1 LIMIT 1"
        ).fetchone()
        return row is not None

    # ------------------------------------------------------------------- async

    async def a(self, fn, *args, **kwargs):
        """Run a store call off the event loop."""
        return await asyncio.to_thread(fn, *args, **kwargs)
