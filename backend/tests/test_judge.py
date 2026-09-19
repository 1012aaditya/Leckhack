import pytest

from app.judge import LexicalJudge, Stance, SupportFinding, judge_with_guard

OPINION = (
    "The State's interest, however weighty, does not override the petitioner's right "
    "to counsel at every critical stage. We therefore reverse the judgment below. "
    "Questions of taxation are not presented by this record."
)


@pytest.fixture
def judge():
    return LexicalJudge()


def test_faithful_claim_is_supported(judge):
    finding = judge_with_guard(
        judge, "the state's interest does not override the right to counsel",
        [OPINION], OPINION,
    )
    assert finding.stance is Stance.SUPPORTS
    assert finding.quote_verified


def test_inverted_claim_is_not_endorsed(judge):
    """The central case: a real opinion cited for the opposite of its holding."""
    finding = judge_with_guard(
        judge, "the state's interest overrides the right to counsel", [OPINION], OPINION
    )
    assert finding.stance is not Stance.SUPPORTS


def test_unrelated_claim_is_not_addressed(judge):
    finding = judge_with_guard(
        judge, "corporations may deduct entertainment expenses", [OPINION], OPINION
    )
    assert finding.stance is Stance.NOT_ADDRESSED
    assert finding.quote == ""


def test_no_passages_means_not_addressed(judge):
    assert judge_with_guard(judge, "anything", [], OPINION).stance is Stance.NOT_ADDRESSED


class FabricatingJudge:
    """Stands in for any judge that invents its evidence."""

    name = "fabricator"
    is_model_based = True

    def judge(self, claim, passages):
        return SupportFinding(
            stance=Stance.SUPPORTS,
            quote="The Court plainly held the opposite of everything.",
            confidence=0.99,
        )


def test_fabricated_quote_is_discarded():
    """The guarantee the project rests on.

    A finding whose quote is not in the opinion is downgraded and the quote
    dropped - the auditor does not get to assert what it cannot show.
    """
    finding = judge_with_guard(FabricatingJudge(), "anything", [OPINION], OPINION)
    assert finding.stance is Stance.UNCLEAR
    assert finding.quote == ""
    assert not finding.quote_verified
    assert "could not be found" in finding.reasoning


def test_lexical_judge_quotes_are_always_verbatim(judge):
    """It selects from the text rather than generating, so it cannot fabricate."""
    for claim in (
        "the state's interest does not override the right to counsel",
        "the judgment below was reversed",
        "taxation questions were presented",
    ):
        finding = judge.judge(claim, [OPINION])
        if finding.quote:
            assert finding.quote in OPINION
