"""Pure image-verdict aggregation rule (design doc §6.2).

Given the per-photo human judgments for a profile, decide whether the photo
set as a whole passes (yes), fails (no), or must be routed to full-profile
review because every photo was judged not_relevant.
"""

from __future__ import annotations

from backend.config import CONFIG
from backend.domain.enums import PhotoLabel, Verdict
from backend.domain.types import VerdictResult


def aggregate_image_verdict(labels: list[PhotoLabel]) -> VerdictResult:
    relevant = _relevant_labels(labels)
    if not relevant:
        return VerdictResult(verdict=None, route_to_review=True)

    yes_count, no_count = _count_yes_no(relevant)
    no_ratio = no_count / len(relevant)
    if yes_count > 0 and no_ratio <= CONFIG.verdict.max_no_ratio:
        return VerdictResult(verdict=Verdict.YES)
    return VerdictResult(verdict=Verdict.NO)


def _relevant_labels(labels: list[PhotoLabel]) -> list[PhotoLabel]:
    """Photos labelled yes or no; not_relevant (and any stray pending) excluded."""
    return [label for label in labels if label in (PhotoLabel.YES, PhotoLabel.NO)]


def _count_yes_no(labels: list[PhotoLabel]) -> tuple[int, int]:
    yes_count = sum(1 for label in labels if label == PhotoLabel.YES)
    no_count = sum(1 for label in labels if label == PhotoLabel.NO)
    return yes_count, no_count
