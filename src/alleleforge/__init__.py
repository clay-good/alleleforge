"""AlleleForge: variant-driven, uncertainty-aware CRISPR edit design.

This top-level package re-exports the version, the global :class:`Settings`,
and the public domain vocabulary from :mod:`alleleforge.types`.

AlleleForge is a *research tool*. It produces ranked hypotheses, not medical
advice, and every off-target nomination it makes is computational and must be
experimentally validated.
"""

from __future__ import annotations

from alleleforge import types
from alleleforge._version import __version__
from alleleforge.config import Settings, get_settings

__all__ = ["Settings", "__version__", "get_settings", "types"]
