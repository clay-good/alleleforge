"""Single source of truth for the AlleleForge version.

The build backend (hatchling) reads ``__version__`` from this module, and the
Rust native extension's ``version()`` is asserted equal to it in the test
suite, proving the toolchain end to end.
"""

from __future__ import annotations

__version__ = "0.1.0.dev0"
