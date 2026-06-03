"""Entry point for the ``aforge`` console script.

This is a deliberately minimal placeholder. Phase 12 replaces it with the full
Typer application (``design``, ``offtarget``, ``resolve``, ``data``, ``bench``).
Keeping it dependency-free for now means installing the core package does not
pull a CLI framework, and the entry point still resolves and reports status.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from alleleforge._native import NATIVE_AVAILABLE
from alleleforge._version import __version__


def app(argv: Sequence[str] | None = None) -> int:
    """Run the placeholder CLI.

    Args:
        argv: Argument vector (excluding the program name). Defaults to
            ``sys.argv[1:]``.

    Returns:
        Process exit code.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in {"-V", "--version", "version"}:
        print(__version__)
        return 0
    native = "available" if NATIVE_AVAILABLE else "not built (pure-Python mode)"
    print(f"aforge {__version__}")
    print(f"native extension: {native}")
    print(
        "The full command surface (design/offtarget/resolve/data/bench) "
        "arrives in Phase 12. See https://github.com/clay-good/alleleforge."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(app())
