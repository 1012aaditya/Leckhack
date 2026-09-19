"""Stage 2: does the cited case actually support the claim?

This is the hard question and the whole point of the tool. A fabricated case
name is easy to catch. A *real* case cited for something it never held looks
fine when you look it up, which is why it slips past people - and why it is
worth building for.

Two implementations, same contract. `ClaudeJudge` reasons about the passages.
`LexicalJudge` is a deterministic fallback with no network dependency, so the
pipeline runs without credentials and the demo survives dead wifi. It is
genuinely weaker and reports itself as such rather than pretending otherwise.

Whichever judge runs, its output passes through `quote_guard` before anyone
sees it. A judge that cannot produce a real quote from the real opinion does
not get to state a finding.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Protocol

from pydantic import BaseModel, Field

from .embeddings import LocalEmbedder
from .quote_guard import verify_quote
from .retrieval import split_sentences

JUDGE_MODEL = "claude-opus-5"


class Stance(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NOT_ADDRESSED = "not_addressed"
    UNCLEAR = "unclear"


class SupportFinding(BaseModel):
    """What a judge concluded about one claim-and-case pair."""

    stance: Stance
    quote: str = Field(
        default="",
        description="Verbatim words from the opinion. Empty if none could be given.",
    )
    reasoning: str = Field(default="", description="One plain sentence.")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    quote_verified: bool = Field(
        default=False, description="Set by the pipeline, never by the judge itself."
    )
    judge: str = ""
    is_model_based: bool = False


class Judge(Protocol):
    name: str
    is_model_based: bool

    def judge(self, claim: str, passages: list[str]) -> SupportFinding: ...


# --------------------------------------------------------------------- prompt

_SYSTEM = """\
You check whether a court opinion supports a specific claim made about it.

You will be given a CLAIM and PASSAGES taken verbatim from the opinion.

Decide one of:
- supports: the passages state or clearly entail the claim
- contradicts: the passages state the opposite of the claim
- not_addressed: the passages simply do not speak to the claim
- unclear: the passages touch on it but do not settle it

Rules you must follow:
1. Judge ONLY from the passages given. Do not use outside knowledge of the case.
2. If you answer supports or contradicts, `quote` MUST be copied character for
   character from the passages. Do not paraphrase, tidy, join fragments, or fix
   punctuation. A quote that is not literally present will be discarded and your
   finding thrown away.
3. If no passage justifies a stance, answer not_addressed with an empty quote.
   That is a correct answer, not a failure.
4. `confidence` reflects how strongly the passages settle the question."""


class ClaudeJudge:
    """Reads the retrieved passages and rules on the claim."""

    name = JUDGE_MODEL
    is_model_based = True

    def __init__(self, api_key: str | None = None, model: str = JUDGE_MODEL) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self._model = model
        self.name = model

    def judge(self, claim: str, passages: list[str]) -> SupportFinding:
        if not passages:
            return SupportFinding(
                stance=Stance.NOT_ADDRESSED,
                reasoning="No passage of the opinion was relevant to this claim.",
                judge=self.name,
                is_model_based=True,
            )

        numbered = "\n\n".join(f"[{i + 1}] {p}" for i, p in enumerate(passages))
        response = self._client.messages.parse(
            model=self._model,
            max_tokens=4000,
            system=_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": f"CLAIM:\n{claim}\n\nPASSAGES:\n{numbered}",
                }
            ],
            output_format=SupportFinding,
        )
        finding = response.parsed_output
        # The judge does not get to vouch for its own quote, and it does not get
        # to set fields the pipeline owns.
        finding.quote_verified = False
        finding.judge = self.name
        finding.is_model_based = True
        return finding


# ----------------------------------------------------------------- fallback

# Words that flip a sentence's meaning. A passage matching the claim closely on
# vocabulary but differing on one of these is the classic "real case, opposite
# holding" pattern this tool exists to catch.
_NEGATORS = {
    "not", "never", "no", "nor", "cannot", "declined", "rejected", "refused",
    "denied", "reversed", "overruled", "without", "fails", "failed", "unless",
}
_WORD = re.compile(r"[a-z']+")


class LexicalJudge:
    """Deterministic fallback. Overlap scoring plus a negation check.

    Honest about what it is: no semantics, no reasoning, just words. It will
    miss paraphrase and it will miss subtle distinctions. Its one real virtue,
    beyond needing no API key, is that its quote is *taken from* the passage
    rather than generated - so it physically cannot fabricate one.
    """

    name = "lexical-fallback"
    is_model_based = False

    def __init__(
        self,
        support_threshold: float = 0.22,
        ambiguity_margin: float = 0.15,
    ) -> None:
        self._embedder = LocalEmbedder()
        self._threshold = support_threshold
        self._margin = ambiguity_margin

    @staticmethod
    def _negations(text: str) -> set[str]:
        return {w for w in _WORD.findall(text.lower()) if w in _NEGATORS}

    @staticmethod
    def _content(text: str) -> str:
        """The sentence with polarity words removed.

        Comparing negation-stripped text isolates *what* a sentence is about
        from *which way* it comes down, so polarity can be judged separately
        instead of being smeared into one similarity score.
        """
        return " ".join(
            w for w in _WORD.findall(text.lower()) if w not in _NEGATORS
        )

    def judge(self, claim: str, passages: list[str]) -> SupportFinding:
        sentences = [s for p in passages for s in split_sentences(p)]
        if not sentences:
            return SupportFinding(
                stance=Stance.NOT_ADDRESSED,
                reasoning="No passage of the opinion was relevant to this claim.",
                judge=self.name,
            )

        query = self._embedder.embed([self._content(claim)])[0]
        matrix = self._embedder.embed([self._content(s) for s in sentences])
        scores = matrix @ query

        claim_negations = self._negations(claim)
        ranked = sorted(
            (
                (float(scores[i]), sentences[i], self._negations(sentences[i]) != claim_negations)
                for i in range(len(sentences))
                if float(scores[i]) >= self._threshold
            ),
            key=lambda row: -row[0],
        )

        if not ranked:
            return SupportFinding(
                stance=Stance.NOT_ADDRESSED,
                reasoning="Nothing in this opinion appears to address that claim.",
                confidence=round(1.0 - float(scores.max()), 2),
                judge=self.name,
            )

        top_score, top_sentence, top_differs = ranked[0]

        if top_differs:
            return SupportFinding(
                stance=Stance.CONTRADICTS,
                quote=top_sentence,
                reasoning=(
                    "The most relevant passage states the opposite of the claim. "
                    "Read the quote and judge for yourself."
                ),
                confidence=round(min(top_score * 1.4, 0.6), 2),
                judge=self.name,
            )

        # A close runner-up of the opposite polarity means this method cannot
        # tell which passage is the holding. Bag-of-words cannot separate "the
        # lease contained a clause purporting to waive X" from "X may be
        # waived". Rather than guess, say so and show the competing passage -
        # an auditor that guesses is the problem it was built to solve.
        opposing = next((row for row in ranked[1:] if row[2]), None)
        if opposing and top_score - opposing[0] < self._margin:
            return SupportFinding(
                stance=Stance.UNCLEAR,
                quote="",
                reasoning=(
                    "Passages point both ways and this offline check cannot tell which "
                    "is the holding. A human should read the opinion."
                ),
                confidence=0.0,
                judge=self.name,
            )

        return SupportFinding(
            stance=Stance.SUPPORTS,
            quote=top_sentence,
            reasoning="A passage of the opinion matches the claim closely.",
            confidence=round(min(top_score * 1.8, 0.85), 2),
            judge=self.name,
        )


# ------------------------------------------------------------------ pipeline


def judge_with_guard(
    judge: Judge, claim: str, passages: list[str], opinion_text: str
) -> SupportFinding:
    """Run a judge, then refuse to publish an unverifiable quote.

    This is the guarantee the whole project rests on. A stance of supports or
    contradicts without a quote that genuinely appears in the opinion is
    downgraded to `unclear` and the quote dropped. The auditor does not get to
    assert something it cannot show.
    """
    finding = judge.judge(claim, passages)

    if finding.stance in (Stance.NOT_ADDRESSED, Stance.UNCLEAR):
        finding.quote = ""
        finding.quote_verified = False
        return finding

    check = verify_quote(finding.quote, opinion_text)
    if check.verified:
        finding.quote_verified = True
        return finding

    return SupportFinding(
        stance=Stance.UNCLEAR,
        quote="",
        reasoning=(
            "A finding was produced but its supporting quote could not be found "
            f"in the opinion, so it was discarded. ({check.reason})"
        ),
        confidence=0.0,
        quote_verified=False,
        judge=finding.judge,
        is_model_based=finding.is_model_based,
    )
