"""FastAPI application for AlleleForge (Phase 13).

:func:`create_app` builds the app; ``app`` is the ASGI instance for
``uvicorn alleleforge.web.api.app:app``.

:func:`serve` runs it, and refuses a non-loopback bind without an API token — the
guard the deployment guide points a reader at, and the reason to prefer it over
running `uvicorn` against the module-level `app`. It is re-exported here because
that is the path the guide names.
"""

from __future__ import annotations

from alleleforge.web.api.app import create_app, serve

__all__ = ["create_app", "serve"]
