"""Command-line interface package for the ``aforge`` command (Phase 12).

Holds the console-script entry point (:func:`run`), which is deliberately *not*
:data:`alleleforge.cli.main.app`.

`pip install alleleforge` is a documented install — "core library (light: pydantic types,
config, model-card parsing)" — and it ships the `aforge` script, because the script is
declared unconditionally while `typer` lives in the `cli` extra. So the first thing a user
of the documented core install saw was::

    Traceback (most recent call last):
      File ".../bin/aforge", line 3, in <module>
        from alleleforge.cli.main import app
      File ".../alleleforge/cli/main.py", line 35, in <module>
        import typer
    ModuleNotFoundError: No module named 'typer'

`main.py` already has `_missing_dependency`, whose docstring says it exists to give an
actionable answer "for the imports that fail before any check runs" — and it could not
help here, because it lives inside the module that cannot load. The one dependency the
command is written in was the one its own remedy could not reach.
"""

from __future__ import annotations

import sys

#: The extra that provides `typer`. Mirrored in `main._EXTRA_FOR_MODULE["typer"]`, which a
#: test pins, because this module cannot import that one to read it.
_CLI_EXTRA = "cli"


def run() -> None:
    """Run the ``aforge`` CLI, or explain what to install.

    Named ``run`` rather than ``main``: this package has a ``main`` *submodule*, so any
    `import alleleforge.cli.main` anywhere in the process rebinds ``alleleforge.cli.main``
    from a function to that module. The console script resolves before that happens, so
    the collision was survivable — and it is the kind of survivable that stops being so
    when something imports the submodule earlier. A test caught it by importing
    `_EXTRA_FOR_MODULE` first.

    Only `typer`'s absence is answered here. Anything else that fails at import time is a
    real defect and is left to raise with its traceback intact — turning every startup
    error into an install hint would hide bugs behind an instruction that does not help.
    """
    try:
        from alleleforge.cli.main import app
    except ImportError as exc:  # pragma: no cover - exercised in a typer-free venv
        if (exc.name or "").split(".")[0] != "typer":
            raise
        print(
            "error: the aforge command needs the optional dependency typer, which is "
            f"not installed: pip install 'alleleforge[{_CLI_EXTRA}]'",
            file=sys.stderr,
        )
        raise SystemExit(69) from exc  # EX_UNAVAILABLE, as ExitCode.UNAVAILABLE uses
    app()
