"""Every scientific operation `alleleforge.benchmark` exports must have a command.

The design entry point has had this guard since three capabilities were found
reachable only from Python (`test_shells_expose_the_library.py`). The benchmark
package had none, and the same thing happened: `generalization_gap` — the
cross-cell-type gap the calibration study reports and the paper plots — was
exported, tested, and reachable from no shell, so a user could score the baseline
on a held-out split but could not ask the question the split exists to answer.

The allowance below is for exports that are not operations a user runs: loaders
that every command already calls, and the primitive the two scoring commands share.
Each is recorded with its reason, and the reverse check keeps the reason honest.
"""

from __future__ import annotations

import inspect

import click
from typer.main import get_command

import alleleforge.benchmark as benchmark
from alleleforge.cli.main import app

#: Exported callables that are not an operation a user would run from a shell.
_NOT_A_COMMAND: dict[str, str] = {
    "build_baseline": "constructs the reference scorer that `run` and `gap` evaluate; "
    "it has no result of its own to print",
    "evaluate_fold": "the shared primitive behind `run` (test fold) and `gap` (two "
    "folds); both callers expose its numbers",
    "get_task": "a lookup; `bench list` is the shell for the task registry",
    "load_dataset": "a loader every command calls; its integrity check is what the "
    "commands report, not a result",
    "load_split": "see `load_dataset`",
    "generalization_gap": "reachable as `bench gap`",
    "run_benchmark": "reachable as `bench run`",
}

#: The command each operation is reachable as, checked to exist.
_REACHABLE_AS: dict[str, str] = {
    "generalization_gap": "gap",
    "run_benchmark": "run",
}


def _exported_callables() -> dict[str, object]:
    return {
        name: obj
        for name in benchmark.__all__
        if callable(obj := getattr(benchmark, name)) and inspect.isfunction(obj)
    }


def _bench_commands() -> dict[str, click.Command]:
    root = get_command(app)
    bench = root.commands["bench"]  # type: ignore[attr-defined]
    return dict(bench.commands)  # type: ignore[attr-defined]


def test_there_is_something_to_check() -> None:
    """Vacuity floor: both sides are populated before anything is compared."""
    exported = _exported_callables()
    assert len(exported) >= 5, sorted(exported)
    assert "generalization_gap" in exported
    assert len(_bench_commands()) >= 4, sorted(_bench_commands())


def test_every_exported_operation_is_accounted_for() -> None:
    unaccounted = sorted(set(_exported_callables()) - set(_NOT_A_COMMAND))
    assert not unaccounted, (
        "`alleleforge.benchmark` exports operations no shell reaches and no "
        f"allowance explains: {unaccounted}. Add a command, or record the reason."
    )


def test_every_claimed_command_exists() -> None:
    commands = _bench_commands()
    missing = {
        operation: command
        for operation, command in _REACHABLE_AS.items()
        if command not in commands
    }
    assert not missing, (
        f"an allowance says these are reachable from a command that does not exist: "
        f"{missing}; `bench` offers {sorted(commands)}"
    )


def test_no_allowance_names_an_export_that_is_gone() -> None:
    """The reverse direction: a reason for a function nobody exports is stale."""
    exported = set(_exported_callables())
    stale = sorted(set(_NOT_A_COMMAND) - exported)
    assert not stale, f"allowance names exports that no longer exist: {stale}"
