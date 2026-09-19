"""Load real Caselaw Access Project data into the local store.

CAP is Harvard Law School Library's digitisation of US case law - roughly 6.4
million cases, 40 million pages, released under CC0 with the original access
restrictions expired in March 2024. See docs/data-sources.md.

Two things here need care.

**Format drift.** CAP has been published in several shapes over the years: the
classic API/bulk form with `casebody.data.opinions`, the 2024 static.case.law
form with `casebody.opinions` directly, and flattened rows on Hugging Face with
a single text column. The normaliser accepts all of them and skips anything it
cannot read rather than failing a whole import. The exact shape of any given
download is NOT verified here - run `scripts/load_cap.py --inspect FILE` against
a real file first, which prints the keys it found and what it made of them.

**Citation keys.** Case citations are normalised with eyecite, the same parser
used on user input. That is deliberate: if the corpus stored "531 U. S. 98" and
the user's text produced "531 U.S. 98", lookups would silently miss. Running
both through one parser makes the keys line up by construction.
"""

from __future__ import annotations

import gzip
import json
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from eyecite import get_citations

from ..store import Store


@dataclass
class NormalizedCase:
    citation: str
    case_name: str | None
    court: str | None
    date_filed: str | None
    text: str
    reporter: str
    """Reporter abbreviation AS EYECITE PARSES IT - e.g. "F.3d", never
    "Federal Reporter 3d Series". Coverage is keyed on this, and coverage is
    what licenses the auditor to say a case does not exist. Key it on a display
    name and a volume you actually hold reads as uncovered."""
    volume: str
    reporter_name: str | None = None
    """Human-readable reporter title, for display only."""
    url: str | None = None


@dataclass
class LoadStats:
    files: int = 0
    seen: int = 0
    loaded: int = 0
    skipped_no_citation: int = 0
    skipped_no_text: int = 0
    skipped_unparsable: int = 0
    volumes: set[tuple[str, str]] = field(default_factory=set)

    def as_dict(self) -> dict:
        return {
            "files": self.files,
            "records_seen": self.seen,
            "cases_loaded": self.loaded,
            "skipped_no_citation": self.skipped_no_citation,
            "skipped_no_text": self.skipped_no_text,
            "skipped_unparsable": self.skipped_unparsable,
            "volumes_covered": len(self.volumes),
        }


# --------------------------------------------------------------- field access


def _first(record: dict, *names: str) -> Any:
    for name in names:
        value = record.get(name)
        if value not in (None, "", [], {}):
            return value
    return None


def _nested_name(value: Any) -> str | None:
    """CAP nests court/reporter as objects in some releases, strings in others."""
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        for key in ("name", "full_name", "name_abbreviation", "short_name"):
            if value.get(key):
                return str(value[key])
    return None


def extract_citation_strings(record: dict) -> list[str]:
    """Pull every candidate citation string out of a record.

    CAP gives `citations` as a list of {type, cite} objects, but flattened
    exports sometimes carry a bare string. Official citations come first
    because they are the ones people cite.
    """
    raw = _first(record, "citations", "citation", "cite")
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]

    official, other = [], []
    for entry in raw if isinstance(raw, list) else [raw]:
        if isinstance(entry, str):
            other.append(entry)
        elif isinstance(entry, dict):
            cite = entry.get("cite") or entry.get("citation")
            if not cite:
                continue
            (official if entry.get("type") == "official" else other).append(str(cite))
    return official + other


def normalize_citation(raw: str) -> tuple[str, str, str] | None:
    """Return (key, reporter, volume) using eyecite, or None if unusable.

    Using eyecite rather than string handling is what guarantees corpus keys
    and user-input keys agree.
    """
    for citation in get_citations(raw):
        groups = getattr(citation, "groups", None) or {}
        volume, reporter, page = (
            groups.get("volume"),
            groups.get("reporter"),
            groups.get("page"),
        )
        if volume and reporter and page:
            return f"{volume} {reporter} {page}", str(reporter), str(volume)
    return None


def extract_text(record: dict) -> str:
    """Assemble the opinion text across CAP's several casebody shapes."""
    # Flattened exports (Hugging Face and similar) put it at the top level.
    flat = _first(record, "text", "plain_text", "opinion_text")
    if isinstance(flat, str) and flat.strip():
        return flat.strip()

    casebody = record.get("casebody")
    if not isinstance(casebody, dict):
        return ""

    # Classic CAP wraps the body in `data`; the 2024 static release does not.
    body = casebody.get("data") if isinstance(casebody.get("data"), dict) else casebody

    parts: list[str] = []
    opinions = body.get("opinions")
    if isinstance(opinions, list):
        for opinion in opinions:
            if isinstance(opinion, dict):
                piece = opinion.get("text") or opinion.get("body") or ""
            else:
                piece = str(opinion)
            if piece and piece.strip():
                parts.append(piece.strip())

    if not parts:
        for key in ("head_matter", "text", "body"):
            value = body.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
                break

    return "\n\n".join(parts)


def normalize_record(record: dict) -> NormalizedCase | None:
    """Turn one CAP record into a row we can store, or None if unusable."""
    if not isinstance(record, dict):
        return None

    parsed = None
    for candidate in extract_citation_strings(record):
        parsed = normalize_citation(candidate)
        if parsed:
            break
    if parsed is None:
        return None

    key, reporter, volume = parsed

    return NormalizedCase(
        citation=key,
        case_name=_first(record, "name_abbreviation", "name", "case_name"),
        court=_nested_name(_first(record, "court")),
        date_filed=_first(record, "decision_date", "date_filed", "decided"),
        text=extract_text(record),
        # Both taken from the parsed citation, never from the record's own
        # metadata, so they always match what a lookup will ask for.
        reporter=reporter,
        volume=volume,
        reporter_name=_nested_name(_first(record, "reporter")),
        url=_first(record, "frontend_url", "url"),
    )


# ------------------------------------------------------------- reading files


def iter_records(path: Path) -> Iterator[dict]:
    """Yield JSON records from whatever shape CAP was downloaded in.

    Handles a directory tree, .zip and .tar.gz archives, gzipped or plain
    JSON Lines, and a plain .json file holding either an array or a single
    object. Anything unreadable is skipped rather than aborting the import.
    """
    path = Path(path)

    if path.is_dir():
        for child in sorted(path.rglob("*")):
            if child.is_file() and child.suffix.lower() in {".json", ".jsonl", ".gz", ".zip", ".tar", ".tgz"}:
                yield from iter_records(child)
        return

    name = path.name.lower()

    if name.endswith(".zip"):
        with zipfile.ZipFile(path) as archive:
            for member in archive.namelist():
                if member.endswith("/") or not member.lower().endswith((".json", ".jsonl")):
                    continue
                with archive.open(member) as handle:
                    yield from _iter_stream(handle.read().decode("utf-8", "replace"))
        return

    if name.endswith((".tar.gz", ".tgz", ".tar")):
        with tarfile.open(path) as archive:
            for member in archive.getmembers():
                if not member.isfile() or not member.name.lower().endswith((".json", ".jsonl")):
                    continue
                handle = archive.extractfile(member)
                if handle:
                    yield from _iter_stream(handle.read().decode("utf-8", "replace"))
        return

    opener = gzip.open if name.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        yield from _iter_stream(handle.read())


def _iter_stream(content: str) -> Iterator[dict]:
    content = content.strip()
    if not content:
        return

    # A whole-file JSON array or object.
    if content[0] in "[{":
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            yield from (r for r in parsed if isinstance(r, dict))
            return
        if isinstance(parsed, dict):
            # Some exports wrap the cases in a envelope.
            for key in ("results", "cases", "data"):
                if isinstance(parsed.get(key), list):
                    yield from (r for r in parsed[key] if isinstance(r, dict))
                    return
            yield parsed
            return

    # Otherwise JSON Lines.
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            yield record


# ------------------------------------------------------------------- loading


def load_cases(
    store: Store,
    records: Iterator[dict],
    source: str = "caselaw-access-project",
    limit: int | None = None,
    reporter_filter: str | None = None,
    require_text: bool = True,
    on_case=None,
) -> LoadStats:
    """Normalise and store CAP records.

    `require_text` defaults to True because a case with no opinion body can be
    existence-checked but cannot answer stage 2, and silently filling the store
    with bodiless records would make "we hold this opinion" untrue.
    """
    stats = LoadStats()
    volume_counts: dict[tuple[str, str], int] = {}

    for record in records:
        if limit is not None and stats.loaded >= limit:
            break
        stats.seen += 1

        case = normalize_record(record)
        if case is None:
            stats.skipped_no_citation += 1
            continue
        if reporter_filter and case.reporter != reporter_filter:
            continue
        if require_text and not case.text.strip():
            stats.skipped_no_text += 1
            continue

        opinion_id = store.upsert_opinion(
            citation=case.citation,
            text=case.text,
            case_name=case.case_name,
            court=case.court,
            date_filed=case.date_filed,
            url=case.url,
            is_synthetic=False,
            source=source,
        )
        stats.loaded += 1

        key = (case.reporter, case.volume)
        stats.volumes.add(key)
        volume_counts[key] = volume_counts.get(key, 0) + 1

        if on_case is not None:
            on_case(opinion_id, case)

    for (reporter, volume), count in volume_counts.items():
        store.record_coverage(reporter, volume, source, count)

    return stats
