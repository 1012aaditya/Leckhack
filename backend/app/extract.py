"""Stage 0: pull citations out of raw text.

This is pure eyecite and runs entirely offline. It deliberately contains no
model call and no network access.

Worth understanding before reading on: extraction cannot tell you whether a
case is real. `999 U.S. 1234` is a perfectly well-formed citation for a case
that has never existed, and eyecite will return it happily. Establishing
whether a case exists is stage 1's job, and it is a database lookup, not a
judgement call.
"""

from __future__ import annotations

from eyecite import clean_text, get_citations

from .models import ExtractedCitation

# eyecite cleaners applied before parsing. `all_whitespace` collapses the
# ragged spacing that PDF extraction produces, which otherwise hides citations
# split across lines.
_CLEANERS = ["all_whitespace"]


def _meta(citation, field: str) -> str | None:
    metadata = getattr(citation, "metadata", None)
    if metadata is None:
        return None
    value = getattr(metadata, field, None)
    return str(value) if value else None


def _group(citation, field: str) -> str | None:
    groups = getattr(citation, "groups", None) or {}
    value = groups.get(field)
    return str(value) if value else None


def extract_citations(text: str) -> list[ExtractedCitation]:
    """Find every citation in `text`, in the order they appear.

    Includes short-form references (`Id.`, `supra`), which are reported but
    flagged as not independently lookupable — they point back at an earlier
    citation rather than naming a case themselves.
    """
    if not text or not text.strip():
        return []

    cleaned = clean_text(text, _CLEANERS)
    found = []

    for citation in get_citations(cleaned):
        start, end = citation.span()
        corrected = None
        if hasattr(citation, "corrected_citation"):
            try:
                corrected = citation.corrected_citation()
            except Exception:  # pragma: no cover - eyecite edge cases
                corrected = None

        found.append(
            ExtractedCitation(
                raw=citation.matched_text(),
                normalized=corrected,
                kind=type(citation).__name__,
                volume=_group(citation, "volume"),
                reporter=_group(citation, "reporter"),
                page=_group(citation, "page"),
                year=_meta(citation, "year"),
                court=_meta(citation, "court"),
                plaintiff=_meta(citation, "plaintiff"),
                defendant=_meta(citation, "defendant"),
                pin_cite=_meta(citation, "pin_cite"),
                start=start,
                end=end,
            )
        )

    return found
