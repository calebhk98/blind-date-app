"""Tests for resolve_final_decision (design doc §6.3)."""

from __future__ import annotations

from backend.domain.enums import Decision, DecisionSource, TriggerReason, Verdict
from backend.domain.types import DecisionResult
from backend.logic.decision import resolve_final_decision


def test_both_yes_no_hard_filter_is_auto_yes() -> None:
    result = resolve_final_decision(Verdict.YES, Verdict.YES, hard_filter_hit=False)
    assert result == DecisionResult(Decision.YES, DecisionSource.AUTO)


def test_both_no_is_auto_no() -> None:
    result = resolve_final_decision(Verdict.NO, Verdict.NO, hard_filter_hit=False)
    assert result == DecisionResult(Decision.NO, DecisionSource.AUTO)


def test_hard_filter_forces_no_even_when_both_yes() -> None:
    result = resolve_final_decision(Verdict.YES, Verdict.YES, hard_filter_hit=True)
    assert result == DecisionResult(Decision.NO, DecisionSource.AUTO)


def test_hard_filter_forces_no_with_split_not_review() -> None:
    result = resolve_final_decision(Verdict.YES, Verdict.NO, hard_filter_hit=True)
    assert result == DecisionResult(Decision.NO, DecisionSource.AUTO)
    assert result.route_to_review is False
    assert result.trigger_reason is None


def test_hard_filter_forces_no_over_other_split_direction() -> None:
    result = resolve_final_decision(Verdict.NO, Verdict.YES, hard_filter_hit=True)
    assert result == DecisionResult(Decision.NO, DecisionSource.AUTO)


def test_split_decision_routes_to_review() -> None:
    result = resolve_final_decision(Verdict.YES, Verdict.NO, hard_filter_hit=False)
    assert result.decision is None
    assert result.source is None
    assert result.route_to_review is True
    assert result.trigger_reason == TriggerReason.SPLIT_DECISION.value


def test_split_decision_other_direction_routes_to_review() -> None:
    result = resolve_final_decision(Verdict.NO, Verdict.YES, hard_filter_hit=False)
    assert result.route_to_review is True
    assert result.trigger_reason == TriggerReason.SPLIT_DECISION.value


def test_all_photos_not_relevant_routes_to_review() -> None:
    result = resolve_final_decision(
        Verdict.PENDING,
        Verdict.YES,
        hard_filter_hit=False,
        all_photos_not_relevant=True,
    )
    assert result.decision is None
    assert result.source is None
    assert result.route_to_review is True
    assert result.trigger_reason == TriggerReason.ALL_NOT_RELEVANT.value


def test_all_photos_not_relevant_does_not_override_both_no() -> None:
    result = resolve_final_decision(
        Verdict.NO,
        Verdict.NO,
        hard_filter_hit=False,
        all_photos_not_relevant=True,
    )
    assert result == DecisionResult(Decision.NO, DecisionSource.AUTO)


def test_all_photos_not_relevant_does_not_override_hard_filter() -> None:
    result = resolve_final_decision(
        Verdict.PENDING,
        Verdict.YES,
        hard_filter_hit=True,
        all_photos_not_relevant=True,
    )
    assert result == DecisionResult(Decision.NO, DecisionSource.AUTO)


def test_all_photos_not_relevant_does_not_override_split() -> None:
    # A real split takes precedence over the all-not-relevant flag when both
    # apply (split is checked first in the precedence order).
    result = resolve_final_decision(
        Verdict.YES,
        Verdict.NO,
        hard_filter_hit=False,
        all_photos_not_relevant=True,
    )
    assert result.trigger_reason == TriggerReason.SPLIT_DECISION.value
