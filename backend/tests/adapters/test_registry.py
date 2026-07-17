"""Tests for backend.adapters.registry: app_id -> adapter class lookup
(design doc §3.2, §4). Importing the registry must fully populate it with no
`if app_id == ...` branching required by callers.
"""

from __future__ import annotations

import pytest

from backend.adapters.bumble import BumbleAdapter
from backend.adapters.hinge import HingeAdapter
from backend.adapters.registry import ADAPTERS, get_adapter_class, register
from backend.adapters.tinder import TinderAdapter


def test_get_adapter_class_known_apps() -> None:
    assert get_adapter_class("tinder") is TinderAdapter
    assert get_adapter_class("bumble") is BumbleAdapter
    assert get_adapter_class("hinge") is HingeAdapter


def test_get_adapter_class_unknown_app_raises() -> None:
    with pytest.raises(KeyError):
        get_adapter_class("nonexistent-app")


def test_register_same_class_twice_is_a_noop() -> None:
    register("tinder", TinderAdapter)
    assert ADAPTERS["tinder"] is TinderAdapter


def test_register_conflicting_class_raises() -> None:
    class OtherAdapter:
        pass

    with pytest.raises(ValueError):
        register("tinder", OtherAdapter)  # type: ignore[arg-type]
