"""Scaffold ("header") adapters for dating apps not yet implemented.

Each module here is a stub subclass of WebBackendAdapter or
AppiumBackendAdapter with the app's signup/login URL and backend
classification documented, and its hooks left as ``NotImplementedError`` /
``# TODO``. These are intentionally NOT imported by ``adapters.registry`` --
they are planning artifacts and manual-signup pointers, not working adapters,
so they can never break ``import backend.adapters.registry``.

To promote one: implement the hooks, move it up to ``backend/adapters/``, and
register it. See ``backend/adapters/DATING_APPS.md`` for the catalog.
"""
