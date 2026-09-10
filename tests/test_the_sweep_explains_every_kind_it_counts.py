"""The integrity sweep counted artifacts it could not explain.

`aforge cache verify` reports what it checked, and a `NOTE` counting what it did not:
artifacts with no pinned checksum, artifacts pinned but absent from this disk. The note
then sent the reader somewhere — "`aforge data list` says which" — and two thirds of those
rows are model **checkpoints**, which that command has never listed. The sentence was
written when the dataset registry was the only one with a shell, and went stale the moment
the model zoo got one, in the round that gave it one.

So the map lives beside the sweep, keyed by `CacheCheck.kind`, and this file derives the
kinds the sweep can actually emit from the sweep's own source rather than listing them.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import typer

from alleleforge.cache_sweep import UNCHECKED, UNCHECKED_REMEDIES
from alleleforge.cli.main import app

_SWEEP = Path(__file__).resolve().parents[1] / "src" / "alleleforge" / "cache_sweep.py"


def _kinds_that_can_be_unchecked() -> set[str]:
    """Return every literal `kind` the sweep pairs with an unchecked status.

    From the producer's AST: a `CacheCheck("dataset", name, "unpinned", ...)` is the fact,
    and a hand-written list of kinds is exactly what went stale here. Namespaces read off
    disk are dynamic and cannot appear — the note explains those as a class, since their
    name is whatever directory a future store creates.
    """
    kinds: set[str] = set()
    for node in ast.walk(ast.parse(_SWEEP.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call) or getattr(node.func, "id", None) != "CacheCheck":
            continue
        args = [a.value if isinstance(a, ast.Constant) else None for a in node.args]
        if len(args) >= 3 and isinstance(args[0], str) and args[2] in UNCHECKED:
            kinds.add(args[0])
    assert kinds, "no unchecked CacheCheck literal found — this check would be vacuous"
    return kinds


def test_every_kind_the_sweep_can_leave_unchecked_has_a_remedy() -> None:
    missing = sorted(_kinds_that_can_be_unchecked() - set(UNCHECKED_REMEDIES))
    assert not missing, (
        f"the sweep can report these kinds as unchecked and nothing tells a reader why: "
        f"{missing}. Add an entry to UNCHECKED_REMEDIES naming the command that explains it."
    )


def test_no_remedy_outlives_the_kind_it_explains() -> None:
    stale = sorted(set(UNCHECKED_REMEDIES) - _kinds_that_can_be_unchecked())
    assert not stale, f"remedies recorded for kinds the sweep no longer reports: {stale}"


def test_every_remedy_names_a_command_that_exists() -> None:
    """The failure this file was written for: a real sentence pointing at the wrong tool."""
    root = typer.main.get_command(app)
    for kind, remedy in UNCHECKED_REMEDIES.items():
        cited = re.findall(r"`aforge ([a-z]+) ([a-z]+)`", remedy)
        assert cited, f"the remedy for {kind!r} names no command: {remedy!r}"
        for group, command in cited:
            sub = root.commands.get(group)  # type: ignore[attr-defined]
            assert sub is not None, f"{kind}: `aforge {group}` does not exist"
            assert command in getattr(sub, "commands", {}), (
                f"{kind}: `aforge {group} {command}` does not exist"
            )


def test_the_command_prints_one_line_per_kind_it_counted(tmp_path: Path) -> None:
    """A count with no explanation is what this replaced."""
    from typer.testing import CliRunner

    result = CliRunner().invoke(app, ["--cache-dir", str(tmp_path), "cache", "verify"])
    assert result.exit_code == 0, result.output + result.stderr
    # A fresh cache dir holds nothing, so every registry row is unchecked — both kinds.
    for kind in ("dataset", "checkpoint"):
        assert f"    {kind}: " in result.stdout, (kind, result.stdout)
    assert "aforge models list" in result.stdout
    assert "aforge data list" in result.stdout
