"""The README's benchmark walkthrough is executed, not just proofread.

Four commands in one block — list the tasks, score the baseline, write a signed result,
render a model-card-gated board — presented as the way to use CRISPR-Bench. Existing guards
check that documented snippets name real flags and import real symbols; none of them runs a
block start to finish, so a renamed subcommand, a changed output flag, or a leaderboard
that rejects the very result `bench run` writes would all survive review of the most-read
file in the repo.

The commands are parsed out of the README and executed through the CLI runner in a
temporary directory, so this fails when the README drifts *or* when the chain breaks. The
glob in the last line is expanded against the files the previous lines actually produced —
which is the point of running it as a sequence: the board is built from the result JSON
that `bench run --out` wrote one line earlier.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app

_README = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")


def _bench_walkthrough() -> list[list[str]]:
    """Return the `aforge bench ...` command lines from the README, in order."""
    for block in re.findall(r"```bash\n(.*?)```", _README, re.S):
        lines = [line.split("#")[0].strip() for line in block.splitlines()]
        commands = [shlex.split(line)[1:] for line in lines if line.startswith("aforge bench")]
        if len(commands) >= 3:
            return commands
    raise AssertionError("the README no longer carries a bench walkthrough")


def test_the_walkthrough_has_the_shape_this_test_assumes() -> None:
    commands = _bench_walkthrough()
    assert commands[0] == ["bench", "list"]
    assert any("leaderboard" in c for c in commands), "no board is built"


def test_every_documented_bench_command_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    for argv in _bench_walkthrough():
        expanded: list[str] = []
        for token in argv:
            if "*" in token:
                matches = sorted(str(p.name) for p in tmp_path.glob(token))
                assert matches, f"{token} matched nothing — the previous step wrote no file"
                expanded.extend(matches)
            else:
                expanded.append(token)
        result = runner.invoke(app, expanded)
        assert result.exit_code == 0, (
            f"`aforge {' '.join(expanded)}` exited {result.exit_code}\n"
            f"{result.output}\n{result.stderr}"
        )


def test_the_board_is_built_from_the_result_the_run_wrote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The chain, not the commands: the leaderboard must accept `bench run`'s own output."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert (
        runner.invoke(app, ["bench", "run", "pe-efficiency", "--out", "result.json"]).exit_code == 0
    )
    board = runner.invoke(
        app, ["bench", "leaderboard", "result.json", "--format", "html", "--out", "board.html"]
    )
    assert board.exit_code == 0, board.output + board.stderr
    rendered = (tmp_path / "board.html").read_text(encoding="utf-8")
    assert "crispr-bench-baseline" in rendered, "the board rendered without the submission"
    assert "synthetic" in rendered, "a synthetic split must be marked as one on the board"
