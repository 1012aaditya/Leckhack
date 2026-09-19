"""Sentence segmentation that understands legal citations.

Shared by retrieval (which chunks opinions) and extraction (which needs the
sentence a citation sits in). Kept in one place because the abbreviation list
is the whole difficulty: splitting on every full stop breaks "Bush v. Gore",
"531 U.S. 98", "Acme Inc." and "No. 21-1234" into nonsense.
"""

from __future__ import annotations

import re

_SENTENCE_END = re.compile(
    r"(?<!\bv)(?<!\bU\.S)(?<!\bNo)(?<!\bInc)(?<!\bCo)(?<!\bLtd)(?<!\bCorp)"
    r"(?<!\bSupp)(?<!\bCir)(?<!\bEd)(?<!\bet\sal)(?<!\b[A-Z])[.!?]+(?=\s|$)"
)


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Character spans of each sentence, terminal punctuation included."""
    spans: list[tuple[int, int]] = []
    position = 0
    for match in _SENTENCE_END.finditer(text):
        end = match.end()
        if text[position:end].strip():
            spans.append((position, end))
        position = end
        while position < len(text) and text[position].isspace():
            position += 1
    if text[position:].strip():
        spans.append((position, len(text)))
    return spans


def split_sentences(text: str) -> list[str]:
    """Sentences with their terminal punctuation preserved.

    Preserving punctuation is not cosmetic: retrieved passages are what the
    judge quotes from, and quote_guard requires a quote to appear verbatim in
    the opinion. Strip the full stops and every honest quote fails the guard.
    """
    return [text[a:b].strip() for a, b in sentence_spans(text) if text[a:b].strip()]


def sentence_containing(text: str, start: int, end: int) -> str:
    """The sentence spanning [start, end), or '' if there is no such sentence."""
    for a, b in sentence_spans(text):
        if a <= start and end <= b:
            return text[a:b].strip()
    return ""
