"""Chunking opinions, indexing them, and finding the passages that matter.

Stage 2 asks whether a cited case supports a claim. Answering that means
locating the parts of a long opinion that bear on the claim, which is what this
module does. It never decides anything - it only narrows.
"""

from __future__ import annotations

import numpy as np

from .embeddings import Embedder, cosine_top_k
from .store import StoredChunk, Store
from .text import split_sentences

# Roughly a long paragraph. Big enough to carry a holding with its reasoning,
# small enough that a retrieved passage is quotable rather than a wall of text.
TARGET_CHUNK_CHARS = 700
OVERLAP_SENTENCES = 1

def chunk_text(text: str, target_chars: int = TARGET_CHUNK_CHARS) -> list[str]:
    """Group sentences into overlapping passages.

    Overlap matters: a holding split across a chunk boundary would otherwise be
    retrievable only in halves, and half a holding is exactly the kind of thing
    that produces a wrong verdict.
    """
    sentences = split_sentences(text)
    if not sentences:
        return []

    chunks: list[str] = []
    current: list[str] = []
    size = 0

    for sentence in sentences:
        if current and size + len(sentence) > target_chars:
            chunks.append(" ".join(current))
            current = current[-OVERLAP_SENTENCES:] if OVERLAP_SENTENCES else []
            size = sum(len(s) for s in current)
        current.append(sentence)
        size += len(sentence)

    if current:
        chunks.append(" ".join(current))
    return chunks


def index_opinion(store: Store, embedder: Embedder, opinion_id: int) -> int:
    """Chunk and embed one opinion. Returns the number of chunks written."""
    opinion = store.get_opinion_by_id(opinion_id)
    if opinion is None or not opinion.text.strip():
        return 0

    pieces = chunk_text(opinion.text)
    if not pieces:
        return 0

    chunk_ids = store.replace_chunks(opinion_id, pieces)
    store.save_embeddings(chunk_ids, embedder.embed(pieces), embedder.name)
    return len(pieces)


def search_opinion(
    store: Store, embedder: Embedder, opinion_id: int, query: str, k: int = 4
) -> list[tuple[StoredChunk, float]]:
    """The k passages of this opinion most relevant to `query`.

    Indexes on demand if the opinion has not been indexed yet, so a freshly
    fetched opinion is searchable without a separate build step.
    """
    chunks, matrix = store.load_embeddings(opinion_id)

    if not chunks:
        if index_opinion(store, embedder, opinion_id) == 0:
            return []
        chunks, matrix = store.load_embeddings(opinion_id)
        if not chunks:
            return []

    # A stored index built by a different embedder is not comparable with this
    # query vector. Rebuild rather than return silently meaningless scores.
    query_vector = embedder.embed([query])[0]
    if matrix.shape[1] != query_vector.shape[0]:
        index_opinion(store, embedder, opinion_id)
        chunks, matrix = store.load_embeddings(opinion_id)
        if not chunks or matrix.shape[1] != query_vector.shape[0]:
            return []

    return [(chunks[i], score) for i, score in cosine_top_k(query_vector, matrix, k)]
