"""Web UI & API (Phase 13).

A FastAPI backend (:mod:`alleleforge.web.api`) exposes the library over HTTP, and
a dependency-free served single-page frontend (``frontend/``) implements the
variant-first journey in the browser. All compute is local and user-controlled:
the app makes no outbound network call and transmits no sequence data externally.
"""

from __future__ import annotations
