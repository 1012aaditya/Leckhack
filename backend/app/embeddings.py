"""Turning text into vectors, with and without an API key.

`VoyageEmbedder` is the real thing - voyage-law-2, a legal-domain model that
leads legal retrieval benchmarks by a wide margin on exactly the long-document
regime court opinions live in.

`LocalEmbedder` is a deterministic lexical fallback with no network dependency.
It is genuinely worse at semantics, and says so. It exists so the pipeline runs
end to end without credentials and so the demo cannot be broken by dead wifi.
Retrieval quality degrades; nothing else changes.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

import numpy as np

_WORD = re.compile(r"[a-z0-9']+")


class Embedder(Protocol):
    name: str
    dim: int
    is_semantic: bool
    """False for the lexical fallback, so callers can caveat their output."""

    def embed(self, texts: list[str]) -> np.ndarray: ...


def _tokens(text: str) -> list[str]:
    words = _WORD.findall(text.lower())
    # Bigrams give the lexical fallback a little word-order sensitivity, which
    # matters when a claim inverts an opinion's meaning ("does not override"
    # versus "does override").
    return words + [f"{a}_{b}" for a, b in zip(words, words[1:])]


class LocalEmbedder:
    """Hashed bag-of-ngrams with sublinear term frequency, L2 normalised.

    Cosine similarity between these vectors approximates lexical overlap. No
    training, no network, identical output on every machine - which makes test
    results reproducible.
    """

    name = "local-hashing-v1"
    is_semantic = False

    def __init__(self, dim: int = 512) -> None:
        self.dim = dim

    def _bucket(self, token: str) -> int:
        digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
        return int.from_bytes(digest, "big") % self.dim

    def embed(self, texts: list[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            counts: dict[int, int] = {}
            for token in _tokens(text):
                bucket = self._bucket(token)
                counts[bucket] = counts.get(bucket, 0) + 1
            for bucket, count in counts.items():
                matrix[row, bucket] = 1.0 + math.log(count)
            norm = np.linalg.norm(matrix[row])
            if norm:
                matrix[row] /= norm
        return matrix


class VoyageEmbedder:
    """voyage-law-2 via the Voyage AI API."""

    name = "voyage-law-2"
    is_semantic = True
    dim = 1024

    def __init__(self, api_key: str, model: str = "voyage-law-2") -> None:
        if not api_key:
            raise ValueError("Voyage embeddings require an API key.")
        self._api_key = api_key
        self.name = model
        self._model = model

    def embed(self, texts: list[str]) -> np.ndarray:
        import httpx

        response = httpx.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"input": texts, "model": self._model, "input_type": "document"},
            timeout=60.0,
        )
        response.raise_for_status()
        payload = response.json()
        vectors = np.array(
            [item["embedding"] for item in payload["data"]], dtype=np.float32
        )
        # Cosine similarity downstream assumes unit vectors; normalise rather
        # than trusting the provider to have done it.
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.dim = vectors.shape[1]
        return vectors / norms


def cosine_top_k(
    query: np.ndarray, matrix: np.ndarray, k: int
) -> list[tuple[int, float]]:
    """Indices and scores of the k rows most similar to `query`."""
    if matrix.size == 0:
        return []
    scores = matrix @ query.reshape(-1)
    k = min(k, scores.shape[0])
    top = np.argpartition(-scores, k - 1)[:k]
    ordered = top[np.argsort(-scores[top])]
    return [(int(i), float(scores[i])) for i in ordered]
