"""Pure final-decision logic (design doc §6.3).

Combines the per-modality verdicts (image, text) and the hard-filter result
into the profile's final decision, or routes the profile to full-profile
human review when the modalities disagree or every photo was not_relevant.
"""

from __future__ import annotations

from backend.domain.enums import Decision, DecisionSource, TriggerReason, Verdict
from backend.domain.types import DecisionResult

_DECIDED = (Verdict.YES, Verdict.NO)


def resolve_final_decision(
    image_verdict: Verdict,
    text_verdict: Verdict,
    hard_filter_hit: bool,
    all_photos_not_relevant: bool = False,
) -> DecisionResult:
    if _both_yes(image_verdict, text_verdict) and not hard_filter_hit:
        return DecisionResult(Decision.YES, DecisionSource.AUTO)
    if _both_no(image_verdict, text_verdict):
        return DecisionResult(Decision.NO, DecisionSource.AUTO)
    if hard_filter_hit:
        return DecisionResult(Decision.NO, DecisionSource.AUTO)
    if _is_split(image_verdict, text_verdict):
        return DecisionResult(
            decision=None,
            source=None,
            route_to_review=True,
            trigger_reason=TriggerReason.SPLIT_DECISION.value,
        )
    if all_photos_not_relevant:
        return DecisionResult(
            decision=None,
            source=None,
            route_to_review=True,
            trigger_reason=TriggerReason.ALL_NOT_RELEVANT.value,
        )
    return DecisionResult(decision=None, source=None)


def _both_yes(image_verdict: Verdict, text_verdict: Verdict) -> bool:
    return image_verdict == Verdict.YES and text_verdict == Verdict.YES


def _both_no(image_verdict: Verdict, text_verdict: Verdict) -> bool:
    return image_verdict == Verdict.NO and text_verdict == Verdict.NO


def _is_split(image_verdict: Verdict, text_verdict: Verdict) -> bool:
    return image_verdict in _DECIDED and text_verdict in _DECIDED
