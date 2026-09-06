"""`aforge bench` must explain a missing optional dependency, not traceback.

On a `pip install "alleleforge[cli]"` — a documented install — every command that
needs the genome stack says so:

    error: this command needs the optional dependency pyfaidx, which is not
    installed: pip install 'alleleforge[genome]'                        (exit 4)

`aforge bench` did not. Its imports reach the genome layer transitively, so all four
subcommands died with a raw `ModuleNotFoundError: No module named 'pyfaidx'` and
exit 1. `_missing_dependency` is the handler that produces the message above; it was
wired into `design`, `batch` and `offtarget`, and `bench` was the fourth place that
needed it.

That a benchmark run needs no reference genome at all is a separate matter — the
import chain reaches `viz.figures`, which does need one at runtime — and is recorded
in `tests/test_core_install_stays_light.py`. This pins the part a user experiences:
the tool explains itself instead of printing a stack trace.
"""

from __future__ import annotations

import builtins
from collections.abc import Iterator

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app


@pytest.fixture
def without_pyfaidx(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Make the benchmark imports fail the way a `[cli]`-only install does.

    Not by evicting modules from `sys.modules`: that forces `alleleforge` to be
    re-imported, which produces duplicate class objects and reset singletons, and
    broke an unrelated config test in the full run while passing in isolation.

    `from X import Y` calls `__import__("X", ..., fromlist=("Y",))` on every
    execution, cached or not, so raising there is enough — and touches nothing
    global. The raised error carries `name="pyfaidx"` because that is what the real
    failure carries and what `_missing_dependency` reads to name the extra.
    """
    real_import = builtins.__import__

    def blocked(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith("alleleforge.benchmark") or name.startswith("pyfaidx"):
            raise ModuleNotFoundError("No module named 'pyfaidx'", name="pyfaidx")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", blocked)
    yield


@pytest.mark.parametrize(
    "argv",
    [
        ["bench", "list"],
        ["bench", "run", "cas9-efficiency"],
        ["bench", "compare", "a.json", "b.json"],
        ["bench", "leaderboard", "a.json"],
    ],
    ids=["list", "run", "compare", "leaderboard"],
)
def test_it_explains_itself(without_pyfaidx: None, argv: list[str]) -> None:
    result = CliRunner().invoke(app, argv)
    combined = result.output + result.stderr
    assert "Traceback" not in combined, combined
    assert "pyfaidx" in combined
    assert "alleleforge[genome]" in combined
    assert result.exit_code == ExitCode.UNAVAILABLE


def test_the_fixture_really_blocks_the_import(without_pyfaidx: None) -> None:
    """Guard the guard: without this the cases above pass on a working install."""
    with pytest.raises(ModuleNotFoundError, match="pyfaidx"):
        from alleleforge.benchmark.tasks import TASKS  # noqa: F401


def test_a_working_install_is_unaffected() -> None:
    """The message must not appear when the dependency is present."""
    result = CliRunner().invoke(app, ["bench", "list"])
    assert result.exit_code == 0, result.output + result.stderr
    assert "alleleforge[genome]" not in result.output
