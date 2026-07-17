"""Tests for aggregate_image_verdict (design doc §6.2)."""

from __future__ import annotations

from backend.config import CONFIG
from backend.domain.enums import PhotoLabel, Verdict
from backend.domain.types import VerdictResult
from backend.logic.verdict import aggregate_image_verdict


def test_all_yes_is_yes() -> None:
    result = aggregate_image_verdict([PhotoLabel.YES, PhotoLabel.YES, PhotoLabel.YES])
    assert result == VerdictResult(verdict=Verdict.YES)


def test_all_no_is_no() -> None:
    result = aggregate_image_verdict([PhotoLabel.NO, PhotoLabel.NO])
    assert result == VerdictResult(verdict=Verdict.NO)


def test_one_yes_rest_no_over_half_is_no() -> None:
    labels = [PhotoLabel.YES, PhotoLabel.NO, PhotoLabel.NO, PhotoLabel.NO]
    result = aggregate_image_verdict(labels)
    assert result == VerdictResult(verdict=Verdict.NO)


def test_exactly_fifty_fifty_is_yes() -> None:
    # Sanity check that the test assumes the shipped default threshold.
    assert CONFIG.verdict.max_no_ratio == 0.5
    labels = [PhotoLabel.YES, PhotoLabel.YES, PhotoLabel.NO, PhotoLabel.NO]
    result = aggregate_image_verdict(labels)
    assert result == VerdictResult(verdict=Verdict.YES)


def test_single_relevant_yes_is_yes() -> None:
    result = aggregate_image_verdict([PhotoLabel.YES])
    assert result == VerdictResult(verdict=Verdict.YES)


def test_single_relevant_no_is_no() -> None:
    result = aggregate_image_verdict([PhotoLabel.NO])
    assert result == VerdictResult(verdict=Verdict.NO)


def test_all_not_relevant_routes_to_review() -> None:
    labels = [PhotoLabel.NOT_RELEVANT, PhotoLabel.NOT_RELEVANT]
    result = aggregate_image_verdict(labels)
    assert result == VerdictResult(verdict=None, route_to_review=True)


def test_not_relevant_excluded_from_denominator_tips_to_yes() -> None:
    # Relevant photos are 1 yes / 1 no (50/50 -> yes); the not_relevant noise
    # must not be counted in the denominator.
    labels = [
        PhotoLabel.NOT_RELEVANT,
        PhotoLabel.YES,
        PhotoLabel.NOT_RELEVANT,
        PhotoLabel.NO,
    ]
    result = aggregate_image_verdict(labels)
    assert result == VerdictResult(verdict=Verdict.YES)


def test_not_relevant_excluded_from_denominator_tips_to_no() -> None:
    # Relevant photos are 1 yes / 2 no (ratio 2/3 > 0.5 -> no).
    labels = [PhotoLabel.NOT_RELEVANT, PhotoLabel.YES, PhotoLabel.NO, PhotoLabel.NO]
    result = aggregate_image_verdict(labels)
    assert result == VerdictResult(verdict=Verdict.NO)


def test_empty_list_routes_to_review() -> None:
    result = aggregate_image_verdict([])
    assert result == VerdictResult(verdict=None, route_to_review=True)
