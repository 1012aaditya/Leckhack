from app.extract import extract_citations


def test_finds_full_citations():
    text = "See Bush v. Gore, 531 U.S. 98 (2000) and Roe v. Wade, 410 U.S. 113 (1973)."
    cites = extract_citations(text)
    assert [c.normalized for c in cites] == ["531 U.S. 98", "410 U.S. 113"]
    assert cites[0].case_name == "Bush v. Gore"
    assert cites[0].year == "2000"


def test_extraction_cannot_detect_fabrication():
    """The central architectural point, pinned as a test.

    A fabricated citation is well-formed, so extraction accepts it. Only a
    database lookup can expose it - which is why stage 1 has no model in it.
    """
    cites = extract_citations("See Smith v. Nowhere, 999 U.S. 1234 (2022).")
    assert len(cites) == 1
    assert cites[0].is_lookupable


def test_short_forms_are_found_but_not_lookupable():
    cites = extract_citations("Bush v. Gore, 531 U.S. 98 (2000). Id. at 99.")
    short = [c for c in cites if c.kind == "IdCitation"]
    assert short and not short[0].is_lookupable


def test_survives_pdf_style_line_breaks():
    text = "The court in Bush v. Gore,\n531 U.S.\n98 (2000), held otherwise."
    assert extract_citations(text)[0].normalized == "531 U.S. 98"


def test_empty_input():
    assert extract_citations("") == []
    assert extract_citations("   \n  ") == []
