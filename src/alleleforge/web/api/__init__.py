"""FastAPI application for AlleleForge (Phase 13).

:func:`alleleforge.web.api.app.create_app` builds the app; ``app`` is the ASGI
instance for ``uvicorn alleleforge.web.api.app:app``.
"""

from __future__ import annotations

from alleleforge.web.api.app import create_app

__all__ = ["create_app"]
