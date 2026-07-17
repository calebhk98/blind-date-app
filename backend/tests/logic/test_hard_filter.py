"""Tests for the pure hard-filter rule (design doc §7.4, issue #20).

TDD: written before backend/logic/hard_filter.py exists.
"""

from __future__ import annotations

from backend.logic.hard_filter import (
    HardFilterCriteria,
    HardFilterFields,
    evaluate_hard_filter,
)


def _fields(age: int | None = None, distance: int | None = None, text: str = "") -> HardFilterFields:
    return HardFilterFields(age=age, distance=distance, text=text)


def _criteria(
    min_age: int | None = None,
    max_age: int | None = None,
    max_distance: int | None = None,
    blocked_keywords: tuple[str, ...] = (),
    required_keywords: tuple[str, ...] = (),
) -> HardFilterCriteria:
    return HardFilterCriteria(
        min_age=min_age,
        max_age=max_age,
        max_distance=max_distance,
        blocked_keywords=blocked_keywords,
        required_keywords=required_keywords,
    )


# --- no criteria set at all -------------------------------------------------


def test_no_criteria_never_filters() -> None:
    fields = _fields(age=99, distance=999, text="anything goes here")
    assert evaluate_hard_filter(fields, _criteria()) is False


# --- age ---------------------------------------------------------------


def test_age_below_min_is_filtered() -> None:
    fields = _fields(age=17)
    assert evaluate_hard_filter(fields, _criteria(min_age=18)) is True


def test_age_above_max_is_filtered() -> None:
    fields = _fields(age=60)
    assert evaluate_hard_filter(fields, _criteria(max_age=45)) is True


def test_age_within_range_is_not_filtered() -> None:
    fields = _fields(age=30)
    assert evaluate_hard_filter(fields, _criteria(min_age=25, max_age=35)) is False


def test_age_equal_to_min_is_allowed() -> None:
    fields = _fields(age=18)
    assert evaluate_hard_filter(fields, _criteria(min_age=18)) is False


def test_age_equal_to_max_is_allowed() -> None:
    fields = _fields(age=45)
    assert evaluate_hard_filter(fields, _criteria(max_age=45)) is False


def test_missing_age_is_not_filtered_even_with_age_criteria_set() -> None:
    fields = _fields(age=None)
    assert evaluate_hard_filter(fields, _criteria(min_age=18, max_age=45)) is False


def test_age_criteria_unset_is_not_enforced() -> None:
    fields = _fields(age=5)
    assert evaluate_hard_filter(fields, _criteria()) is False


# --- distance ------------------------------------------------------------


def test_distance_over_max_is_filtered() -> None:
    fields = _fields(distance=50)
    assert evaluate_hard_filter(fields, _criteria(max_distance=25)) is True


def test_distance_equal_to_max_is_allowed() -> None:
    fields = _fields(distance=25)
    assert evaluate_hard_filter(fields, _criteria(max_distance=25)) is False


def test_distance_under_max_is_not_filtered() -> None:
    fields = _fields(distance=10)
    assert evaluate_hard_filter(fields, _criteria(max_distance=25)) is False


def test_missing_distance_is_not_filtered_even_with_max_distance_set() -> None:
    fields = _fields(distance=None)
    assert evaluate_hard_filter(fields, _criteria(max_distance=25)) is False


def test_max_distance_unset_is_not_enforced() -> None:
    fields = _fields(distance=10000)
    assert evaluate_hard_filter(fields, _criteria()) is False


# --- blocked keywords ------------------------------------------------------


def test_blocked_keyword_present_is_filtered() -> None:
    fields = _fields(text="looking for something casual, married but curious")
    assert evaluate_hard_filter(fields, _criteria(blocked_keywords=("married",))) is True


def test_no_blocked_keyword_present_is_not_filtered() -> None:
    fields = _fields(text="looking for something serious")
    assert evaluate_hard_filter(fields, _criteria(blocked_keywords=("married",))) is False


def test_blocked_keywords_empty_is_not_enforced() -> None:
    fields = _fields(text="married and looking")
    assert evaluate_hard_filter(fields, _criteria(blocked_keywords=())) is False


# --- required keywords -------------------------------------------------


def test_missing_required_keyword_is_filtered() -> None:
    fields = _fields(text="i love hiking")
    assert evaluate_hard_filter(fields, _criteria(required_keywords=("vaccinated",))) is True


def test_present_required_keyword_is_not_filtered() -> None:
    fields = _fields(text="fully vaccinated, i love hiking")
    assert evaluate_hard_filter(fields, _criteria(required_keywords=("vaccinated",))) is False


def test_all_required_keywords_must_be_present() -> None:
    fields = _fields(text="fully vaccinated")
    criteria = _criteria(required_keywords=("vaccinated", "nonsmoker"))
    assert evaluate_hard_filter(fields, criteria) is True


def test_required_keywords_empty_is_not_enforced() -> None:
    fields = _fields(text="")
    assert evaluate_hard_filter(fields, _criteria(required_keywords=())) is False


# --- combined ------------------------------------------------------------


def test_combined_criteria_any_violation_filters() -> None:
    fields = _fields(age=30, distance=10, text="clean bio")
    criteria = _criteria(min_age=18, max_age=99, max_distance=5)
    assert evaluate_hard_filter(fields, criteria) is True


def test_combined_criteria_all_pass_is_not_filtered() -> None:
    fields = _fields(age=30, distance=10, text="fully vaccinated, no drama")
    criteria = _criteria(
        min_age=18,
        max_age=99,
        max_distance=25,
        blocked_keywords=("drama queen",),
        required_keywords=("vaccinated",),
    )
    assert evaluate_hard_filter(fields, criteria) is False
