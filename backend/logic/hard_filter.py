"""Pure hard-filter rule (design doc §3, §7.4, issue #20).

``evaluate_hard_filter`` is the single source of truth for whether a
profile's normalized fields trip any *enforced* hard-filter criterion. A
criterion left at its "unset" value (``None`` for age/distance bounds, an
empty tuple for keyword lists) is not enforced -- mirrors
``backend.config.HardFilterConfig``'s own "unset = not enforced" contract.

``HardFilterCriteria`` deliberately mirrors ``HardFilterConfig`` rather than
reusing it directly: this module must stay pure (no config/env reads), and
the live criteria are runtime-editable and persisted in the ``settings``
table (see ``backend.db.repository.get_hard_filter_settings``, issue #21),
not read from ``CONFIG`` at evaluation time. Callers translate whichever
source (env-config defaults or DB-stored overrides) into this shape.

A profile with no value for a given field (age/distance unknown) can never
violate the corresponding bound -- there's nothing to compare, so it passes
that criterion rather than being filtered on missing data.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class HardFilterFields:
    """Normalized per-profile fields the hard-filter rule reads.

    ``text`` is expected pre-lowered and pre-assembled (bio + prompts, etc.)
    by the caller -- this module never knows how a profile's text was put
    together, only that it's a single lowercase string to search.
    """

    age: int | None = None
    distance: int | None = None
    text: str = ""


@dataclass(frozen=True)
class HardFilterCriteria:
    """Mirrors ``backend.config.HardFilterConfig`` field-for-field."""

    min_age: int | None = None
    max_age: int | None = None
    max_distance: int | None = None
    blocked_keywords: tuple[str, ...] = field(default_factory=tuple)
    required_keywords: tuple[str, ...] = field(default_factory=tuple)


def evaluate_hard_filter(fields: HardFilterFields, criteria: HardFilterCriteria) -> bool:
    """True when ``fields`` violates any criterion enforced by ``criteria``."""
    return (
        _violates_age(fields, criteria)
        or _violates_distance(fields, criteria)
        or _contains_blocked_keyword(fields, criteria)
        or _missing_required_keyword(fields, criteria)
    )


def _violates_age(fields: HardFilterFields, criteria: HardFilterCriteria) -> bool:
    if fields.age is None:
        return False
    if criteria.min_age is not None and fields.age < criteria.min_age:
        return True
    if criteria.max_age is not None and fields.age > criteria.max_age:
        return True
    return False


def _violates_distance(fields: HardFilterFields, criteria: HardFilterCriteria) -> bool:
    if fields.distance is None or criteria.max_distance is None:
        return False
    return fields.distance > criteria.max_distance


def _contains_blocked_keyword(fields: HardFilterFields, criteria: HardFilterCriteria) -> bool:
    return any(keyword in fields.text for keyword in criteria.blocked_keywords)


def _missing_required_keyword(fields: HardFilterFields, criteria: HardFilterCriteria) -> bool:
    return any(keyword not in fields.text for keyword in criteria.required_keywords)
