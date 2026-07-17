"""Recompute + persist verdicts and final decisions (design doc §6.2, §6.3).

Side-effecting orchestration only: every rule this module enforces is
delegated to the pure functions in ``backend.logic.verdict`` /
``backend.logic.decision`` -- this module's only job is loading the right
rows via ``backend.db.repository``, calling those pure functions, and
writing the result back. Never duplicate the aggregation/decision rules here
(design doc §4: single source of truth).

``backend.db.repository`` is imported lazily inside each function body
(rather than at module top level) purely so this module always imports
cleanly regardless of that module's own dependency footprint/build order.
"""

from __future__ import annotations

import sqlite3
import uuid

from backend.domain.enums import Decision, DecisionSource, PhotoLabel, UserDecision, Verdict
from backend.domain.types import DecisionResult
from backend.logic.decision import resolve_final_decision
from backend.logic.verdict import aggregate_image_verdict


def on_photo_judged(
    conn: sqlite3.Connection, profile_id: str, photo_id: str, label: PhotoLabel
) -> DecisionResult:
    """Persist a photo label, and -- once every photo on the profile has been
    judged (design doc §6.2: ``aggregate_image_verdict`` cannot itself tell
    "still pending" apart from "explicitly not_relevant", both are simply
    absent from its relevant-labels count, so this module gates on that
    itself rather than calling the aggregation rule prematurely) --
    recompute image_verdict via the pure aggregation rule and re-resolve the
    final decision. While photos remain pending, only the individual label is
    persisted; verdicts/decisions are left untouched.
    """
    from backend.db import repository

    repository.set_photo_label(conn, photo_id, label.value)
    labels = _photo_labels(conn, profile_id)
    if not _all_photos_judged(labels):
        return DecisionResult(decision=None, source=None)

    verdict_result = aggregate_image_verdict(labels)
    if verdict_result.verdict is not None:
        repository.set_image_verdict(conn, profile_id, verdict_result.verdict.value)
    return _resolve_and_persist(conn, profile_id, verdict_result.route_to_review)


def on_text_judged(conn: sqlite3.Connection, profile_id: str, verdict: Verdict) -> DecisionResult:
    """Persist the text verdict and re-resolve the final decision."""
    from backend.db import repository

    if verdict not in (Verdict.YES, Verdict.NO):
        raise ValueError(f"text verdict must be yes or no, got {verdict!r}")
    repository.set_text_verdict(conn, profile_id, verdict.value)
    return _resolve_and_persist(conn, profile_id, _all_photos_not_relevant(conn, profile_id))


def evaluate_profile(conn: sqlite3.Connection, profile_id: str) -> DecisionResult:
    """Re-derive the current ``DecisionResult`` for ``profile_id`` from its
    persisted verdicts, without writing anything.

    Used internally by the judged-photo/text paths and by the review route
    to recover ``trigger_reason`` at review time -- the pure rule is only
    ever evaluated in this one place (design doc §4: single source of
    truth), never re-implemented at the call site.
    """
    from backend.db import repository

    profile = repository.get_profile(conn, profile_id)
    if profile is None:
        raise ValueError(f"unknown profile_id: {profile_id}")
    image_verdict = Verdict(profile["image_verdict"])
    text_verdict = Verdict(profile["text_verdict"])
    hard_filter_hit = bool(profile["hard_filter_hit"])
    all_not_relevant = _all_photos_not_relevant(conn, profile_id)
    return resolve_final_decision(image_verdict, text_verdict, hard_filter_hit, all_not_relevant)


def record_review_decision(
    conn: sqlite3.Connection, profile_id: str, user_decision: UserDecision
) -> DecisionResult:
    """Write the human review outcome and set the final decision (design doc
    §6.3 review path). Only valid for a profile currently routed to review
    (split decision or all-photos-not-relevant); fails loud otherwise.
    """
    from backend.db import repository

    pending = evaluate_profile(conn, profile_id)
    if not pending.route_to_review:
        raise ValueError(f"profile {profile_id} is not pending review")
    assert pending.trigger_reason is not None  # resolve_final_decision always sets it alongside route_to_review

    profile = repository.get_profile(conn, profile_id)
    assert profile is not None  # evaluate_profile already validated existence
    image_verdict = Verdict(profile["image_verdict"])
    text_verdict = Verdict(profile["text_verdict"])

    decision = Decision(user_decision.value)
    repository.insert_review_decision(
        conn,
        review_id=str(uuid.uuid4()),
        profile_id=profile_id,
        trigger_reason=pending.trigger_reason,
        image_verdict_at_review=image_verdict.value,
        text_verdict_at_review=text_verdict.value,
        user_decision=user_decision.value,
    )
    repository.set_final_decision(conn, profile_id, decision.value, DecisionSource.REVIEW.value)
    return DecisionResult(decision=decision, source=DecisionSource.REVIEW)


def _photo_labels(conn: sqlite3.Connection, profile_id: str) -> list[PhotoLabel]:
    from backend.db import repository

    return [PhotoLabel(row["label"]) for row in repository.get_photos(conn, profile_id)]


def _all_photos_judged(labels: list[PhotoLabel]) -> bool:
    return all(label != PhotoLabel.PENDING for label in labels)


def _all_photos_not_relevant(conn: sqlite3.Connection, profile_id: str) -> bool:
    """True only once every photo on the profile has a decided label (none
    still ``pending``) *and* every one of those decided labels is
    ``not_relevant``. Deliberately conservative: a profile with photos still
    awaiting judgment is never treated as "all not relevant" just because it
    happens to have no yes/no labels *yet* (see ``on_photo_judged``'s
    docstring for why that distinction can't be made inside the pure
    aggregation rule itself).
    """
    labels = _photo_labels(conn, profile_id)
    if not _all_photos_judged(labels):
        return False
    return aggregate_image_verdict(labels).route_to_review


def _resolve_and_persist(
    conn: sqlite3.Connection, profile_id: str, all_photos_not_relevant: bool
) -> DecisionResult:
    from backend.db import repository

    profile = repository.get_profile(conn, profile_id)
    if profile is None:
        raise ValueError(f"unknown profile_id: {profile_id}")
    image_verdict = Verdict(profile["image_verdict"])
    text_verdict = Verdict(profile["text_verdict"])
    hard_filter_hit = bool(profile["hard_filter_hit"])
    result = resolve_final_decision(
        image_verdict, text_verdict, hard_filter_hit, all_photos_not_relevant
    )
    if result.decision is not None:
        assert result.source is not None
        repository.set_final_decision(conn, profile_id, result.decision.value, result.source.value)
    return result
