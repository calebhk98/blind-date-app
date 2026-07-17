"""app_id -> adapter class registry (design doc §3.2, §4).

Keeps the orchestrator app-agnostic: it looks up
``get_adapter_class(app_id)`` and never branches on ``if app_id ==
"tinder"``. Each app module calls ``register()`` at the bottom of its own
file, at import time. Importing *this* module imports every app module, so
``ADAPTERS`` is always fully populated as soon as ``backend.adapters.registry``
is imported -- regardless of which module a caller happens to import first.
"""

from __future__ import annotations

from backend.adapters.base import DatingAppAdapter

ADAPTERS: dict[str, type[DatingAppAdapter]] = {}


def register(app_id: str, cls: type[DatingAppAdapter]) -> None:
    """Register ``cls`` as the adapter for ``app_id``.

    Fails loud (design doc §4) on a conflicting duplicate registration
    (different class for the same app_id) rather than silently overwriting;
    re-registering the same class for the same app_id is a harmless no-op so
    modules may be imported more than once without error.
    """
    existing = ADAPTERS.get(app_id)
    if existing is not None and existing is not cls:
        raise ValueError(
            f"app_id {app_id!r} already registered to {existing.__name__}, "
            f"cannot register {cls.__name__}"
        )
    ADAPTERS[app_id] = cls


def get_adapter_class(app_id: str) -> type[DatingAppAdapter]:
    """Look up the adapter class for ``app_id``.

    Raises ``KeyError`` (fail loud) for an unknown app_id rather than
    returning ``None``.
    """
    try:
        return ADAPTERS[app_id]
    except KeyError:
        raise KeyError(f"no adapter registered for app_id {app_id!r}") from None


# Import every app adapter module so each one's register() call runs and
# ADAPTERS is fully populated as soon as this module is imported (design doc
# §4: single source of truth for app_id -> class). Placed after
# register()/ADAPTERS are defined because each app module imports `register`
# back from this module at its own import time (see module docstring).
from backend.adapters import bumble as _bumble  # noqa: E402,F401
from backend.adapters import hinge as _hinge  # noqa: E402,F401
from backend.adapters import tinder as _tinder  # noqa: E402,F401
