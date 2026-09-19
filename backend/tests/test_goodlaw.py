from app.goodlaw import Treatment, check_good_law, classify_treatment
from app.store import Store


def test_overruling_is_detected(store):
    target = store.get_opinion("42 F.3d 100")
    report = check_good_law(store, target.id)
    assert report.has_negative_treatment
    assert report.findings[0].treatment is Treatment.OVERRULED
    assert report.findings[0].quote_verified


def test_following_is_not_negative_treatment(store):
    target = store.get_opinion("58 F.3d 900")
    report = check_good_law(store, target.id)
    assert not report.has_negative_treatment
    assert "not a guarantee" in report.summary


def test_treatment_of_another_case_is_not_attributed_here():
    """An opinion overruling some other case must not taint this one.

    Scanning a whole document for the word "overruled" would attribute any
    overruling anywhere to whatever case is being checked.
    """
    citing = (
        "We cite Alvarez v. Northgate, 42 F.3d 100, with approval throughout. "
        "Separately, an unrelated line of authority is overruled today."
    )
    treatment, _ = classify_treatment(citing, "42 F.3d 100", "Alvarez v. Northgate")
    assert treatment is not Treatment.OVERRULED


def test_no_citing_cases_is_reported_as_unchecked():
    store = Store(":memory:")
    opinion_id = store.upsert_opinion("1 U.S. 1", text="body", case_name="A v. B")
    report = check_good_law(store, opinion_id)
    assert report.checked
    assert report.citing_count == 0
    assert "could not be checked" in report.summary
    store.close()


def test_unknown_opinion_is_not_checked():
    store = Store(":memory:")
    assert not check_good_law(store, 999).checked
    store.close()
