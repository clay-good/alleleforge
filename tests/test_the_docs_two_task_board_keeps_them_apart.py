"""The docs' multi-task board must not rank two tasks in one table.

`docs/api/cli.md` documents a chain that scores two different tasks and renders one board:

    aforge bench run cas9-outcome --out outcome.json
    aforge bench run offtarget-classification --out offtarget.json
    aforge bench leaderboard outcome.json offtarget.json --format html --out board.html

Those results are not comparable — one is a KL divergence on a distribution task, the
other an AUROC on a classification task — and the spec says a rank never crosses a
comparison group. A refactor that merged the groups would produce a single ranked table
putting one above the other as though one model beat another, which is the most plausible
way for this board to become actively misleading.

The chain used to lead with `cas9-efficiency`. The reference baseline predicts one
constant, so its Spearman is undefined there and the row is listed unranked — an honest
board and a poor demonstration of ranking, which is what this file is about.

The chain is executed rather than described, so this covers both the documented workflow
and the grouping rule. Running it verbatim is also how one confirms the docs still work:
the two-task form appears in no other test.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app

_DOC = (Path(__file__).resolve().parents[1] / "docs" / "api" / "cli.md").read_text(encoding="utf-8")


def _documented_two_task_chain() -> list[list[str]]:
    """The `bench run`/`bench leaderboard` lines the CLI reference documents, in order."""
    commands = []
    for line in _DOC.splitlines():
        stripped = line.split("#")[0].strip()
        if re.match(r"^aforge bench (run|leaderboard) ", stripped):
            commands.append(stripped.split()[1:])
    runs = [c for c in commands if c[1] == "run" and "--out" in c]
    boards = [
        c
        for c in commands
        if c[1] == "leaderboard" and len([t for t in c if t.endswith(".json")]) >= 2
    ]
    assert len(runs) >= 2 and boards, "the CLI reference no longer documents a two-task board"
    return [*runs[:2], boards[0]]


def test_the_documented_chain_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    for argv in _documented_two_task_chain():
        result = runner.invoke(app, argv)
        assert result.exit_code == 0, (
            f"`aforge {' '.join(argv)}` exited {result.exit_code}\n{result.output}{result.stderr}"
        )
    assert (tmp_path / "board.html").is_file()


def test_two_tasks_render_as_two_groups(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    for argv in _documented_two_task_chain():
        assert runner.invoke(app, argv).exit_code == 0
    board = (tmp_path / "board.html").read_text(encoding="utf-8")

    assert "cas9-outcome" in board and "offtarget-classification" in board
    # Each group carries its own primary metric in its own header row.
    headers = re.findall(r"<th>([a-z0-9_]+)</th>", board)
    assert "kl" in headers and "auroc" in headers
    for row in re.findall(r"<tr>(.*?)</tr>", board, re.S):
        cells = re.findall(r"<th>([a-z0-9_]+)</th>", row)
        assert not ("kl" in cells and "auroc" in cells), (
            "one header row carries both metrics — the two tasks were ranked together"
        )


def test_neither_result_outranks_the_other(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both entries are rank 1 of their own group; there is no cross-task ordering."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    for argv in _documented_two_task_chain():
        assert runner.invoke(app, argv).exit_code == 0
    board = (tmp_path / "board.html").read_text(encoding="utf-8")
    ranks = re.findall(r"<td>(\d+)</td><td>crispr-bench-baseline</td>", board)
    assert ranks == ["1", "1"], f"expected each group to rank its own entry first, got {ranks}"
