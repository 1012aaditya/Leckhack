import pytest

from app.quote_guard import normalize, verify_quote

SOURCE = (
    "The State’s interest — however weighty — does not override "
    "the petitioner’s right to counsel at every critical stage."
)


def test_accepts_exact_quote():
    assert verify_quote("does not override the petitioner's right", SOURCE).verified


def test_accepts_messy_whitespace():
    assert verify_quote("does  not\n override   the petitioner's right", SOURCE).verified


def test_accepts_typographic_variants():
    assert verify_quote("The State's interest - however weighty", SOURCE).verified


def test_rejects_fabricated_quote():
    result = verify_quote("clearly overrides the petitioner's right to counsel", SOURCE)
    assert not result.verified
    assert "do not appear" in result.reason


def test_rejects_quote_too_short_to_be_meaningful():
    assert not verify_quote("the right", SOURCE).verified


@pytest.mark.parametrize("quote", ["", "   ", "\n"])
def test_rejects_empty(quote):
    assert not verify_quote(quote, SOURCE).verified


def test_rejects_when_no_source_available():
    assert not verify_quote("does not override the petitioner's right", "").verified


def test_normalize_never_drops_words():
    assert len(normalize(SOURCE).split()) == len(SOURCE.split())
