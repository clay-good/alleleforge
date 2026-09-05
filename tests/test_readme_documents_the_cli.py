"""The README must name every command the CLI actually ships.

`aforge verify` shipped complete — provenance completeness plus artifact re-hashing,
the mechanism that turns provenance from a record into a checkable contract — and
appeared in neither the README nor `docs/`. An undiscoverable feature is, for every
practical purpose, an unshipped one, and no test could tell: the command worked, its
own tests passed, and the gap lived entirely in the prose.

This pins the mechanical half of the claim. It cannot tell whether the documentation
is *good*, only whether each command is mentioned at all — which is exactly the check
that was missing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.cli.main import app

_ROOT = Path(__file__).resolve().parents[1]


def _command_names() -> list[str]:
    """Return every registered top-level command name."""
    return sorted(
        info.name or (info.callback.__name__ if info.callback else "")
        for info in (*app.registered_commands, *app.registered_groups)
    )


def test_every_cli_command_is_named_in_the_docs() -> None:
    names = _command_names()
    assert names, "no commands discovered — the introspection above is wrong, not the docs"

    prose = (_ROOT / "README.md").read_text()
    for path in (_ROOT / "docs").rglob("*.md"):
        prose += path.read_text()

    missing = [name for name in names if f"aforge {name}" not in prose]
    assert not missing, f"CLI commands documented nowhere: {missing}"


@pytest.mark.parametrize("removed", ["verify", "offtarget"])
def test_the_check_would_notice_a_missing_command(removed: str) -> None:
    """Guard the guard: the assertion above must depend on the prose, not pass blindly."""
    prose = (_ROOT / "README.md").read_text().replace(f"aforge {removed}", "")
    for path in (_ROOT / "docs").rglob("*.md"):
        prose += path.read_text().replace(f"aforge {removed}", "")
    assert f"aforge {removed}" not in prose
    assert removed in _command_names()
