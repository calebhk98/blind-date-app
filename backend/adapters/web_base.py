"""WebBackendAdapter (design doc §3.2): shared base for Playwright-driven
adapters (Tinder, Bumble).

Playwright is imported lazily, only inside the one method that actually
starts a browser (``_ensure_context``), never at module import time. That
keeps ``import backend.adapters.web_base`` (and anything built on it)
working with no ``playwright`` package installed -- required because
playwright is intentionally not installed in this environment.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from backend.adapters._shared import ProfileParseError, SwipedStore, _CommonAdapterBase
from backend.config import CONFIG

__all__ = [
    "WebBackendAdapter",
    "ProfileParseError",
    "SwipedStore",
    "parse_xhtml_fragment",
]


def parse_xhtml_fragment(raw: str) -> ET.Element:
    """Parse a well-formed XHTML fragment into an ``ElementTree`` element.

    Generic to any web (Playwright) adapter -- not app-specific -- so it
    lives here rather than being duplicated per app. Stdlib-only (no bs4 /
    lxml dependency): fixtures and any production markup this feeds on must
    be well-formed (self-closed void tags, one root element).

    TODO: verify against live DOM -- real markup is not guaranteed
    well-formed XHTML. If live pages break this parser, prefer extracting
    already-structured data via Playwright's ``eval_on_selector_all``
    instead of shipping a hand-rolled HTML parser.

    Raises ``ProfileParseError`` on malformed markup rather than silently
    returning partial data (design doc §4: fail loud).

    Namespaces are stripped from every tag so subclasses can match on bare
    names (``.//p``): a browser's ``XMLSerializer`` stamps the XHTML namespace
    onto every element, which would otherwise make ``{ns}p`` != ``p``.
    """
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ProfileParseError(f"malformed profile markup: {exc}") from exc
    for element in root.iter():
        if isinstance(element.tag, str) and "}" in element.tag:
            element.tag = element.tag.split("}", 1)[1]
    return root


class WebBackendAdapter(_CommonAdapterBase):
    """Playwright-backed adapter base.

    Subclasses implement the abstract hooks defined on ``_CommonAdapterBase``
    (``_login_impl``, ``_fetch_raw``, ``_fetch_detail_raw``, ``_parse_profile``,
    ``_do_swipe``) with app-specific selectors; they must not touch the
    idempotent-swipe/retry/fetch-parse plumbing, which lives in exactly one
    place (``_shared._CommonAdapterBase``).
    """

    def __init__(self, app_id: str, swiped_store: SwipedStore) -> None:
        super().__init__(app_id, swiped_store)
        self._playwright: Any | None = None
        self._context: Any | None = None

    @property
    def session_dir(self) -> Path:
        """Persistent per-app browser session storage (cookies/tokens),
        design doc §4: ``CONFIG.storage.session_dir/<app_id>``.
        """
        return CONFIG.storage.session_dir / self.app_id

    def _ensure_context(self) -> Any:
        """Lazily start Playwright and return a persistent browser context
        rooted at ``session_dir``.

        ``playwright`` is imported here -- and only here -- so the module
        loads fine with no playwright installed.
        """
        if self._context is not None:
            return self._context
        from playwright.sync_api import sync_playwright  # lazy import: see module docstring

        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        launch_kwargs: dict[str, Any] = {
            "user_data_dir": str(self.session_dir),
            "headless": True,
        }
        # Use a pre-installed browser binary when configured (sandboxed envs
        # ship Chromium at a fixed path instead of downloading it).
        if CONFIG.automation.chromium_executable_path:
            launch_kwargs["executable_path"] = CONFIG.automation.chromium_executable_path
        self._context = self._playwright.chromium.launch_persistent_context(**launch_kwargs)
        return self._context

    def close(self) -> None:
        """Tear down the browser context / Playwright process, if started."""
        if self._context is not None:
            self._context.close()
            self._context = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
