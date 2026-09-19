from app.quote_guard import verify_quote
from app.retrieval import chunk_text, index_opinion, search_opinion
from app.text import sentence_containing, split_sentences

OPINION = " ".join(
    f"This is sentence number {i} of the opinion and it continues for some length."
    for i in range(50)
)


def test_citation_abbreviations_do_not_end_sentences():
    text = "See Bush v. Gore, 531 U.S. 98 (2000). Acme Inc. won. No. 21-4 was denied."
    assert split_sentences(text) == [
        "See Bush v. Gore, 531 U.S. 98 (2000).",
        "Acme Inc. won.",
        "No. 21-4 was denied.",
    ]


def test_terminal_punctuation_is_preserved():
    assert split_sentences("One thing. Another thing.") == ["One thing.", "Another thing."]


def test_every_chunk_verifies_against_the_source():
    """Chunking must be quote-preserving.

    Retrieved passages are what the judge quotes from, and quote_guard demands
    a verbatim match. If chunking mangles the text, every honest quote fails
    the guard and stage 2 silently produces nothing.
    """
    chunks = chunk_text(OPINION)
    assert len(chunks) > 1
    assert all(verify_quote(chunk, OPINION).verified for chunk in chunks)


def test_sentence_containing_finds_the_right_span():
    text = "First sentence here. Second sentence here. Third one."
    index = text.index("Second")
    assert sentence_containing(text, index, index + 6) == "Second sentence here."


def test_search_ranks_the_relevant_passage_first(store, embedder):
    opinion = store.get_opinion("58 F.3d 900")
    hits = search_opinion(store, embedder, opinion.id, "self-help eviction lockout", k=2)
    assert hits
    assert "self-help" in hits[0][0].text.lower()


def test_search_indexes_on_demand(store, embedder):
    opinion = store.get_opinion("42 F.3d 100")
    store.replace_chunks(opinion.id, [])
    assert search_opinion(store, embedder, opinion.id, "implied warranty", k=1)


def test_opinion_without_text_indexes_to_nothing(store, embedder):
    opinion_id = store.upsert_opinion("9 U.S. 9", text="")
    assert index_opinion(store, embedder, opinion_id) == 0
