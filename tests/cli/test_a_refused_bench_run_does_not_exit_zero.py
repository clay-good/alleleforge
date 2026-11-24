"""The `bench` family's eleven refusals, none of which proved it exited non-zero.

This is the second file closing the class R691 named: in `cli/main.py`, deleting a
`raise typer.Exit(...)` leaves the `_echo_err` line above it running, so the error prints
with the right wording and the process exits **0**. Every test asserting on stderr text
keeps passing. R691 pinned three sites (`design`, `verify`); this closes the eleven in
`bench run`, `bench gap`, `bench compare` and `bench leaderboard`.

The `bench` family is where exit 0 costs most in this project, and not because benchmarks
are important in the abstract. The repository's own release criteria turn on these
numbers, and `tests/cli/test_a_synthetic_benchmark_number_says_so_everywhere.py` and
`test_an_edited_benchmark_number_is_refused.py` exist because a benchmark figure that
travels without its provenance is this project's central honesty risk. These commands are
run from scripts, in a loop, over several tasks — exactly the shape where nobody reads
stderr and the exit code is the only signal. A `bench run` that prints "unknown task"
and exits 0 writes no result file and reports success, and the aggregation step that
follows it either skips a model silently or reads a stale file from a previous run. The
leaderboard then shows a number attributed to a run that never happened.

Nine of the eleven are reachable straight from the shell. Two are not: the
`SplitIntegrityError` arms in `bench run` and `bench gap` fire when a frozen split fails
its hash check, and neither command takes a `--splits-dir`, so the only way to reach them
from outside is to corrupt a split inside the installed package. Those two are pinned by
injecting the exception at the seam the command imports it from, which is what is being
tested anyway: not that `load_split` can detect tampering (`tests/benchmark` covers
that), but that this CLI maps that detection onto a non-zero exit instead of printing
and continuing.

Found by deleting each refusal (`scripts/mutate.py --mode raise`); all eleven survived
`tests/cli`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app

#: A real task and a real frozen split, so a refusal below is the one being provoked and
#: not an unrelated lookup failing first.
_TASK = "cas9-efficiency"
_VERSION = "v1"


def _output(result: object) -> str:
    """Both streams, since these refusals write to stderr and the runner splits them."""
    return getattr(result, "output", "") + (getattr(result, "stderr", "") or "")


# -- bench run / bench gap: the task lookup ------------------------------------


@pytest.mark.parametrize("command", ["run", "gap"])
def test_an_unknown_bench_task_is_a_usage_error(runner: CliRunner, command: str) -> None:
    """Both commands carry their own copy of the handler, so both are asserted.

    A typo'd task name is the likeliest mistake here: these are hyphenated identifiers
    copied from `bench list` or a leaderboard row.
    """
    result = runner.invoke(app, ["bench", command, "not-a-task", "--split-version", _VERSION])

    assert result.exit_code == ExitCode.USAGE, (
        f"`bench {command}` on an unknown task exited {result.exit_code}. Exit 0 here "
        "means a scripted sweep records a success for a task it never scored.",
        _output(result),
    )
    out = _output(result)
    assert "unknown task" in out, out
    assert _TASK in out, (
        "the refusal does not list the known tasks, so a caller with a stale identifier "
        "has nothing to correct it to",
        out,
    )


@pytest.mark.parametrize("command", ["run", "gap"])
def test_a_missing_split_version_is_missing_data_not_usage(runner: CliRunner, command: str) -> None:
    """A real task at a version that does not exist.

    `MISSING_DATA` rather than `USAGE` is the distinction worth pinning: the caller's
    command is well-formed and the corpus is what is absent, and a script can tell those
    apart to decide whether to fetch data or fix its arguments.
    """
    result = runner.invoke(app, ["bench", command, _TASK, "--split-version", "v9999"])

    assert result.exit_code == ExitCode.MISSING_DATA, (result.exit_code, _output(result))
    assert "no split" in _output(result), _output(result)


# -- bench run / bench gap: the integrity arm ----------------------------------


@pytest.mark.parametrize("command", ["run", "gap"])
def test_a_split_that_fails_its_integrity_check_is_refused(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    """A tampered frozen split must stop the run, not be reported and scored past.

    Injected at the seam rather than by corrupting a file, because neither command takes
    a `--splits-dir` and the shipped splits live inside the package. What is under test
    is the CLI's mapping, not the detection: a split whose hashes no longer match is the
    one case where continuing would attach a real-looking score to a corpus nobody can
    reproduce, which is the failure the signing machinery exists to prevent.
    """
    from alleleforge.benchmark import splits as splits_module

    def _tampered(*_args: object, **_kwargs: object) -> None:
        raise splits_module.SplitIntegrityError("recorded hash ab12 != computed cd34")

    monkeypatch.setattr(splits_module, "load_split", _tampered)

    result = runner.invoke(app, ["bench", command, _TASK, "--split-version", _VERSION])

    assert result.exit_code == ExitCode.MISSING_DATA, (
        f"`bench {command}` scored past a failed integrity check with exit {result.exit_code}",
        _output(result),
    )
    out = _output(result)
    assert "integrity check failed" in out, out
    # The arm has its own wording, so a test matching only the sibling's message would
    # pass with this one deleted.
    assert "no split" not in out, out


# -- bench gap: the fold argument ----------------------------------------------


def test_an_unknown_fold_is_a_usage_error(runner: CliRunner) -> None:
    """`bench gap` takes two fold names, and a wrong one is the caller's input.

    The source comment records that this once exited 2 for a *degenerate* fold as well,
    which called a well-formed question a usage error and disagreed with `bench run` on
    the same fold of the same task. This pins the remaining case — a fold name that is
    not a fold at all — without re-asserting the behaviour that comment says was wrong.
    """
    result = runner.invoke(
        app,
        [
            "bench",
            "gap",
            _TASK,
            "--split-version",
            _VERSION,
            "--in-context-fold",
            "train",
            "--held-out-fold",
            "not-a-fold",
        ],
    )

    assert result.exit_code == ExitCode.USAGE, (result.exit_code, _output(result))
    assert "error" in _output(result).lower(), _output(result)


# -- bench compare / bench leaderboard: the result files -----------------------


def _a_result_json(tmp_path: Path, name: str) -> Path:
    """A file that exists and parses but is not a `BenchmarkResult`.

    Separating "absent" from "present but not a result" is the point: they are different
    exit codes (`MISSING_DATA` vs `USAGE`) because they are different user mistakes — a
    path that is wrong, versus a file that is the wrong thing.
    """
    path = tmp_path / name
    path.write_text(json.dumps({"not": "a benchmark result"}))
    return path


def test_bench_compare_on_a_missing_file_exits_missing_data(
    runner: CliRunner, tmp_path: Path
) -> None:
    present = _a_result_json(tmp_path, "present.json")
    result = runner.invoke(app, ["bench", "compare", str(tmp_path / "gone.json"), str(present)])

    assert result.exit_code == ExitCode.MISSING_DATA, (result.exit_code, _output(result))
    assert "not found" in _output(result), _output(result)


def test_bench_compare_on_a_file_that_is_not_a_result_exits_usage(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Valid JSON, wrong shape — which is what a mis-globbed path looks like."""
    left = _a_result_json(tmp_path, "left.json")
    right = _a_result_json(tmp_path, "right.json")
    result = runner.invoke(app, ["bench", "compare", str(left), str(right)])

    assert result.exit_code == ExitCode.USAGE, (result.exit_code, _output(result))
    out = _output(result)
    assert "not a valid benchmark result" in out, out
    assert left.name in out, (
        "the refusal does not name which of the two files was unreadable",
        out,
    )


def test_bench_leaderboard_on_a_missing_file_exits_missing_data(
    runner: CliRunner, tmp_path: Path
) -> None:
    """The command that builds the published board, so exit 0 publishes a short board.

    `leaderboard` takes a list of results. Without the guard a missing path is announced
    and skipped, and the board renders from whatever remained — fewer models than the
    caller passed, with nothing in the artifact saying so.
    """
    result = runner.invoke(app, ["bench", "leaderboard", str(tmp_path / "gone.json")])

    assert result.exit_code == ExitCode.MISSING_DATA, (result.exit_code, _output(result))
    assert "not found" in _output(result), _output(result)


def test_bench_leaderboard_on_a_file_that_is_not_a_result_exits_usage(
    runner: CliRunner, tmp_path: Path
) -> None:
    result = runner.invoke(
        app, ["bench", "leaderboard", str(_a_result_json(tmp_path, "board.json"))]
    )

    assert result.exit_code == ExitCode.USAGE, (result.exit_code, _output(result))
    assert "not a valid result JSON" in _output(result), _output(result)


# -- the invariant, stated once for the family ---------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["bench", "run", "not-a-task", "--split-version", _VERSION],
        ["bench", "run", _TASK, "--split-version", "v9999"],
        ["bench", "gap", "not-a-task", "--split-version", _VERSION],
        ["bench", "gap", _TASK, "--split-version", "v9999"],
        ["bench", "compare", "/nonexistent/a.json", "/nonexistent/b.json"],
        ["bench", "leaderboard", "/nonexistent/a.json"],
    ],
    ids=["run-task", "run-version", "gap-task", "gap-version", "compare", "leaderboard"],
)
def test_no_bench_refusal_exits_zero(runner: CliRunner, argv: list[str]) -> None:
    """Deliberately weaker than the tests above, and for a different job.

    Each test above pins one exact code; this one would catch *any* of the eleven
    deletions on the paths it covers. A refusal that exits 0 is the defect; which
    non-zero code it chooses is a separate contract, asserted per-command above.
    """
    result = runner.invoke(app, argv)
    assert result.exit_code != 0, (
        f"`aforge {' '.join(argv)}` refused and still exited 0",
        _output(result),
    )
