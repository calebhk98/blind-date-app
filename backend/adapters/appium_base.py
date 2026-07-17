"""AppiumBackendAdapter (design doc §3.2): shared base for Appium-driven
native-app adapters (Hinge).

The Appium client is imported lazily, only inside the one method that
actually starts a driver session (``_ensure_driver``), never at module
import time. That keeps ``import backend.adapters.appium_base`` working
with no ``Appium-Python-Client`` package installed -- required because it is
intentionally not installed in this environment.
"""

from __future__ import annotations

from typing import Any

from backend.adapters._shared import ProfileParseError, SwipedStore, _CommonAdapterBase

__all__ = ["AppiumBackendAdapter", "ProfileParseError", "SwipedStore"]


class AppiumBackendAdapter(_CommonAdapterBase):
    """Appium-backed adapter base.

    Subclasses implement the abstract hooks defined on ``_CommonAdapterBase``
    (``_login_impl``, ``_fetch_raw``, ``_fetch_detail_raw``, ``_parse_profile``,
    ``_do_swipe``) with app-specific locators; they must not touch the
    idempotent-swipe/retry/fetch-parse plumbing, which lives in exactly one
    place (``_shared._CommonAdapterBase``).
    """

    #: Appium server URL. A deployment concern, not an app concern (design
    #: doc §4: no app-specific logic outside its own adapter).
    APPIUM_SERVER_URL = "http://localhost:4723"

    def __init__(self, app_id: str, swiped_store: SwipedStore) -> None:
        super().__init__(app_id, swiped_store)
        self._driver: Any | None = None

    def _capabilities(self) -> dict[str, Any]:
        """App-specific Appium desired capabilities.

        Default is empty; subclasses override with their platform/app
        package details. Not an abstract hook -- adapters that need no
        extra capabilities (unlikely, but keeps the base generic) may skip
        overriding it.
        """
        return {}

    def _ensure_driver(self) -> Any:
        """Lazily start an Appium driver session for this app.

        The ``appium`` client is imported here -- and only here -- so the
        module loads fine with no Appium-Python-Client installed.
        """
        if self._driver is not None:
            return self._driver
        from appium import webdriver  # lazy import: see module docstring
        from appium.options.common import AppiumOptions

        options = AppiumOptions()
        for key, value in self._capabilities().items():
            options.set_capability(key, value)
        self._driver = webdriver.Remote(self.APPIUM_SERVER_URL, options=options)
        return self._driver

    def _find(self, by: Any, value: str) -> Any:
        """Element-finding helper against the live driver session."""
        return self._ensure_driver().find_element(by, value)

    def close(self) -> None:
        """Tear down the driver session, if started."""
        if self._driver is not None:
            self._driver.quit()
            self._driver = None
