"""The CAP ingestion path, against all the shapes CAP has shipped in."""

import gzip
import json
from pathlib import Path

import pytest

from app.ingest.cap import (
    extract_citation_strings,
    extract_text,
    iter_records,
    load_cases,
    normalize_citation,
    normalize_record,
)
from app.store import Store

SAMPLE = Path(__file__).resolve().parents[1] / "fixtures" / "cap_sample.jsonl"

CLASSIC = {
    "name_abbreviation": "A v. B",
    "citations": [{"type": "official", "cite": "42 F.3d 100"}],
    "casebody": {"data": {"opinions": [{"type": "majority", "text": "The holding."}]}},
}
STATIC_2024 = {
    "name_abbreviation": "C v. D",
    "citations": [{"type": "official", "cite": "58 F.3d 900"}],
    "casebody": {"opinions": [{"type": "majority", "text": "Another holding."}]},
}
FLATTENED = {
    "name_abbreviation": "E v. F",
    "citations": "91 F.3d 415",
    "text": "A flattened opinion body.",
}


@pytest.fixture
def db():
    store = Store(":memory:")
    yield store
    store.close()


@pytest.mark.parametrize(
    "record,expected",
    [(CLASSIC, "The holding."), (STATIC_2024, "Another holding."),
     (FLATTENED, "A flattened opinion body.")],
)
def test_text_extracted_from_every_casebody_shape(record, expected):
    assert extract_text(record) == expected


def test_all_opinions_are_kept_not_just_the_majority():
    record = {
        "citations": [{"type": "official", "cite": "1 U.S. 1"}],
        "casebody": {"data": {"opinions": [
            {"type": "majority", "text": "The majority view."},
            {"type": "dissent", "text": "The dissent."},
        ]}},
    }
    text = extract_text(record)
    assert "The majority view." in text and "The dissent." in text


def test_official_citation_is_preferred_over_parallel():
    record = {"citations": [
        {"type": "parallel", "cite": "1994 WL 99999"},
        {"type": "official", "cite": "42 F.3d 100"},
    ]}
    assert extract_citation_strings(record)[0] == "42 F.3d 100"


def test_citation_key_matches_what_eyecite_produces_for_user_input():
    """Corpus keys and lookup keys must agree, or every lookup silently misses."""
    from app.extract import extract_citations

    key, reporter, volume = normalize_citation("42 F.3d 100")
    from_user = extract_citations("See Alvarez v. Northgate, 42 F.3d 100 (1994).")[0]
    assert key == f"{from_user.volume} {from_user.reporter} {from_user.page}"
    assert (reporter, volume) == (from_user.reporter, from_user.volume)


def test_reporter_for_coverage_comes_from_the_citation_not_the_metadata():
    """Regression: coverage keyed on a display name splits a volume we hold.

    CAP records the reporter as "Federal Reporter 3d Series" while citations
    say "F.3d". Keying coverage on the former makes covers("F.3d", "42") false
    for a volume fully loaded, so real absences get reported as unchecked.
    """
    record = dict(CLASSIC, reporter={"full_name": "Federal Reporter 3d Series",
                                     "short_name": "F.3d"})
    case = normalize_record(record)
    assert case.reporter == "F.3d"
    assert case.reporter_name == "Federal Reporter 3d Series"


def test_record_without_a_usable_citation_is_skipped():
    assert normalize_record({"name_abbreviation": "No Cite", "text": "body"}) is None
    assert normalize_record({"citations": [{"cite": "not a citation"}]}) is None


def test_reads_jsonl_json_array_and_gzip(tmp_path):
    records = [CLASSIC, STATIC_2024]

    jsonl = tmp_path / "a.jsonl"
    jsonl.write_text("\n".join(json.dumps(r) for r in records))
    assert len(list(iter_records(jsonl))) == 2

    array = tmp_path / "b.json"
    array.write_text(json.dumps(records))
    assert len(list(iter_records(array))) == 2

    wrapped = tmp_path / "c.json"
    wrapped.write_text(json.dumps({"results": records}))
    assert len(list(iter_records(wrapped))) == 2

    gz = tmp_path / "d.jsonl.gz"
    gz.write_bytes(gzip.compress("\n".join(json.dumps(r) for r in records).encode()))
    assert len(list(iter_records(gz))) == 2


def test_malformed_lines_are_skipped_not_fatal(tmp_path):
    path = tmp_path / "mixed.jsonl"
    path.write_text(json.dumps(CLASSIC) + "\n{ not json at all\n" + json.dumps(FLATTENED))
    assert len(list(iter_records(path))) == 2


def test_load_records_coverage_and_text(db):
    stats = load_cases(db, iter_records(SAMPLE), complete_volumes=True)
    assert stats.loaded == 3
    assert db.covers("F.3d", "42")
    assert not db.covers("F.2d", "900")
    assert "implied warranty" in db.get_opinion("42 F.3d 100").text


def test_partial_load_is_not_treated_as_complete(db):
    """Holding part of a volume proves nothing about the rest of it.

    record_coverage fires for any volume with at least one case, so without an
    explicit assertion of completeness the auditor would call real cases
    fabricated purely because they were not in the slice downloaded.
    """
    load_cases(db, iter_records(SAMPLE))
    assert db.has_volume("F.3d", "42")
    assert not db.covers("F.3d", "42")


def test_completeness_survives_a_later_partial_load(db):
    load_cases(db, iter_records(SAMPLE), complete_volumes=True)
    load_cases(db, iter_records(SAMPLE))
    assert db.covers("F.3d", "42")


def test_loaded_cases_are_not_marked_synthetic(db):
    load_cases(db, iter_records(SAMPLE))
    assert db.get_opinion("42 F.3d 100").is_synthetic is False


def test_cases_without_text_are_skipped_by_default(db):
    record = {"citations": [{"type": "official", "cite": "5 U.S. 5"}], "casebody": {}}
    stats = load_cases(db, iter([record]))
    assert stats.loaded == 0 and stats.skipped_no_text == 1
    assert db.get_opinion("5 U.S. 5") is None


def test_reporter_filter_and_limit(db):
    assert load_cases(db, iter_records(SAMPLE), reporter_filter="F.2d").loaded == 0
    assert load_cases(db, iter_records(SAMPLE), limit=2).loaded == 2


def test_synthetic_corpus_is_marked_as_such(db):
    """Invented text must never enter the corpus labelled as a real record.

    The bundled sample is real CAP *format* with fictional content. Loading it
    without the flag would put made-up cases in the store indistinguishable
    from genuine ones - the exact failure this tool exists to catch, committed
    by the tool itself.
    """
    load_cases(db, iter_records(SAMPLE), is_synthetic=True, source="sample")
    assert db.get_opinion("42 F.3d 100").is_synthetic is True
    assert db.has_synthetic_corpus() is True


def test_real_load_is_not_marked_synthetic(db):
    load_cases(db, iter_records(SAMPLE))
    assert db.has_synthetic_corpus() is False
