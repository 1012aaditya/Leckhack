import numpy as np
import pytest

from app.store import Store


@pytest.fixture
def db():
    store = Store(":memory:")
    yield store
    store.close()


def test_upsert_is_idempotent(db):
    first = db.upsert_opinion("1 U.S. 1", text="body", case_name="A v. B")
    second = db.upsert_opinion("1 U.S. 1", text="body", case_name="A v. B")
    assert first == second


def test_metadata_update_never_wipes_stored_text(db):
    """A metadata-only refresh must not destroy an opinion we already fetched."""
    db.upsert_opinion("1 U.S. 1", text="the full opinion")
    db.upsert_opinion("1 U.S. 1", court="SCOTUS")
    opinion = db.get_opinion("1 U.S. 1")
    assert opinion.text == "the full opinion"
    assert opinion.court == "SCOTUS"


def test_embeddings_round_trip(db):
    opinion_id = db.upsert_opinion("1 U.S. 1", text="x")
    chunk_ids = db.replace_chunks(opinion_id, ["alpha", "beta"])
    vectors = np.arange(16, dtype=np.float32).reshape(2, 8)
    db.save_embeddings(chunk_ids, vectors, "m")
    chunks, matrix = db.load_embeddings(opinion_id)
    assert [c.text for c in chunks] == ["alpha", "beta"]
    assert np.allclose(matrix, vectors)


def test_mismatched_vector_count_is_rejected(db):
    opinion_id = db.upsert_opinion("1 U.S. 1", text="x")
    chunk_ids = db.replace_chunks(opinion_id, ["a", "b"])
    with pytest.raises(ValueError):
        db.save_embeddings(chunk_ids, np.zeros((1, 4), dtype=np.float32), "m")


def test_citing_opinions_are_newest_first(db):
    target = db.upsert_opinion("1 U.S. 1", text="x")
    older = db.upsert_opinion("2 U.S. 2", text="x", date_filed="1990-01-01")
    newer = db.upsert_opinion("3 U.S. 3", text="x", date_filed="2020-01-01")
    db.add_citation_edge(older, target)
    db.add_citation_edge(newer, target)
    assert [o.citation for o in db.citing_opinions(target)] == ["3 U.S. 3", "2 U.S. 2"]
