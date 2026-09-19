"""The auditor's check on its own work.

An auditing tool that invents its findings is worse than no tool at all, and
it is the first thing a sceptical judge will probe. So every quote the system
attributes to a court opinion passes through here before it can be displayed:
if the quoted words are not actually in the source document, the finding is
discarded rather than shown.

This is a deterministic guard wrapped around a probabilistic component. It has
no model in it and cannot itself hallucinate.
"""

from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel

# Typographic variants that mean the same thing. A model reproducing a quote
# will often normalise a curly apostrophe or an em dash without changing a
# single word, and rejecting that would be pedantry rather than a safeguard.
_CHAR_EQUIVALENTS = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-",
    "—": "-", "―": "-", "−": "-",
    " ": " ", " ": " ", " ": " ",
    "…": "...",
}

_WHITESPACE = re.compile(r"\s+")


class QuoteCheck(BaseModel):
    """Result of verifying one quote against its claimed source."""

    quote: str
    verified: bool
    reason: str
    start: int | None = None
    end: int | None = None


def normalize(text: str) -> str:
    """Fold away differences that do not change the words.

    Unicode-normalises, maps typographic variants to ASCII, collapses runs of
    whitespace, and lowercases. It never removes or reorders words, so two
    strings that normalise equal really do say the same thing.
    """
    text = unicodedata.normalize("NFKC", text)
    text = "".join(_CHAR_EQUIVALENTS.get(char, char) for char in text)
    text = _WHITESPACE.sub(" ", text)
    return text.strip().lower()


def verify_quote(quote: str, source_text: str, min_words: int = 4) -> QuoteCheck:
    """Confirm `quote` appears verbatim in `source_text`.

    `min_words` exists because a two-word fragment will match almost any long
    document by coincidence, which would make the guard meaningless. Quotes
    shorter than this are rejected rather than waved through.

    Offsets in the result are into the NORMALIZED source, so they locate the
    passage for retrieval and are not safe for slicing the raw original.
    """
    if not quote or not quote.strip():
        return QuoteCheck(quote=quote, verified=False, reason="Quote was empty.")

    if len(quote.split()) < min_words:
        return QuoteCheck(
            quote=quote,
            verified=False,
            reason=f"Quote too short to verify (under {min_words} words).",
        )

    if not source_text or not source_text.strip():
        return QuoteCheck(
            quote=quote, verified=False, reason="No source text available to check against."
        )

    needle = normalize(quote)
    haystack = normalize(source_text)
    index = haystack.find(needle)

    if index == -1:
        return QuoteCheck(
            quote=quote,
            verified=False,
            reason="These words do not appear in the source opinion.",
        )

    return QuoteCheck(
        quote=quote,
        verified=True,
        reason="Found verbatim in the source opinion.",
        start=index,
        end=index + len(needle),
    )
