"""The board's *structure* is content, and nothing was checking it.

A statement-deletion sweep removed thirteen `lines.append(...)` / `parts.append(...)`
calls from `benchmark/leaderboard.py` one at a time and the whole suite stayed green for
every one. They are not decoration:

* `| ---: | :--- | ... |`, the row that makes the lines above and below it a **table**.
  Delete it and every markdown renderer — GitHub, the docs site, an issue comment —
  shows the ranked board as a run of pipe-separated prose. The numbers are all still
  there and the artifact most likely to be published, linked and screenshotted is no
  longer a table.
* `### <group label>`, the heading that says which comparison group a table belongs to.
  A board carries several, and the module prints a note saying *why* they cannot be
  compared with each other — with the headings gone, the reader is handed consecutive
  tables with no way to tell which is which, directly under a sentence insisting they
  are different.
* `</body></html>`, and the blank lines that separate every block in markdown, where a
  heading that is not followed by one is not a heading at all.

The existing board tests read the rendered text for *facts* — a disclaimer, a version,
the synthetic marking, a rank order. Every one of them passes on a document whose
structure has collapsed, because the strings they look for are still in it. This file
checks the shape instead.
"""

from __future__ import annotations

import re

import pytest

from alleleforge.benchmark.leaderboard import Leaderboard
from tests.benchmark.test_the_leaderboard_states_what_it_is import _board

_SEPARATOR = re.compile(r"^\|[\s:-]+\|[\s:|-]*$")


@pytest.fixture
def board() -> Leaderboard:
    return _board(("cas9-efficiency", "pe-efficiency"))


def _markdown(board: Leaderboard) -> list[str]:
    return board.render_markdown().split("\n")


def test_the_fixture_renders_more_than_one_group() -> None:
    """The premise for the heading checks: one group needs no label to tell apart."""
    board = _board(("cas9-efficiency", "pe-efficiency"))
    groups = [g for task in board.tasks for g, _ in board.comparison_groups(task)]
    assert len(groups) > 1, groups


def test_every_header_row_is_followed_by_its_separator(board: Leaderboard) -> None:
    """Without this row the lines above and below it are not a table to any renderer."""
    lines = _markdown(board)
    headers = [
        i
        for i, line in enumerate(lines)
        if line.startswith("| Rank |") or line.startswith("| Model |")
    ]
    assert headers, "the board rendered no table at all"
    for i in headers:
        assert _SEPARATOR.match(lines[i + 1] or ""), (
            f"the header on line {i} is followed by {lines[i + 1]!r}, not a separator row"
        )


def test_every_group_is_named_by_a_heading(board: Leaderboard) -> None:
    text = board.render_markdown()
    for task in board.tasks:
        for group, _ in board.comparison_groups(task):
            assert f"### {group.label()}" in text, group.label()


def test_every_task_is_named_by_a_heading(board: Leaderboard) -> None:
    """The level above, so a group heading cannot stand in for its task's."""
    text = board.render_markdown()
    for task in board.tasks:
        assert f"## {task}" in text, task


def test_every_heading_is_followed_by_a_blank_line(board: Leaderboard) -> None:
    """A heading with content jammed under it does not render as one."""
    lines = _markdown(board)
    for i, line in enumerate(lines):
        if line.startswith("#"):
            assert lines[i + 1] == "", f"{line!r} is followed by {lines[i + 1]!r}"


def test_every_table_block_is_closed_by_a_blank_line(board: Leaderboard) -> None:
    """Otherwise the next heading or note is swallowed into the table above it."""
    lines = _markdown(board)
    rows = [i for i, line in enumerate(lines) if line.startswith("|")]
    assert rows, "the board rendered no table at all"
    for i in rows:
        following = lines[i + 1] if i + 1 < len(lines) else ""
        assert following.startswith("|") or following == "", (
            f"the table row on line {i} is followed by {following!r}"
        )


def test_the_html_board_is_a_closed_document(board: Leaderboard) -> None:
    page = board.render_html()
    assert page.rstrip().endswith("</body></html>"), page[-120:]
    for task in board.tasks:
        for group, _ in board.comparison_groups(task):
            assert f"<h3>{group.label()}</h3>" in page, group.label()


def test_every_block_starts_on_a_blank_line(board: Leaderboard) -> None:
    """Markdown needs the blank line *before* a heading or a table, not only after.

    The remaining deletions are the blank lines that close a prose note — the
    incomparable-groups sentence, the contested-group warning, the "not ranked"
    label — each of which is immediately followed by a heading or a table header.
    Without the separator those blocks are glued to the paragraph above and render as
    part of it: the warning absorbs the table it was written to qualify.
    """
    lines = _markdown(board)
    for i, line in enumerate(lines):
        if i == 0:
            continue
        previous = lines[i - 1]
        if line.startswith("#"):
            assert previous == "", f"the heading {line!r} follows {previous!r}"
        elif line.startswith("|") and not previous.startswith("|"):
            assert previous == "", f"the table starting {line!r} follows {previous!r}"


@pytest.fixture
def two_group_board() -> Leaderboard:
    """One task, two comparison groups and a contested one.

    Both prose blocks before a table — the incomparable-groups note and the
    contested-group warning — are emitted only for a shape the board above never
    builds: the first needs a task holding more than one group, the second a group
    whose rows disagree about the split they measured. Their trailing blank lines are
    what separates each from the table it introduces, so without this fixture those
    two separators have no case at all.
    """
    from datetime import UTC, datetime

    from alleleforge.benchmark._canon import content_hash
    from alleleforge.benchmark.baseline import build_baseline
    from alleleforge.benchmark.leaderboard import Submission
    from alleleforge.benchmark.runner import BenchmarkResult, run_benchmark
    from alleleforge.benchmark.splits import load_split
    from alleleforge.benchmark.tasks import get_task

    task = get_task("cas9-efficiency")
    split, dataset = load_split("cas9-efficiency")
    baseline = run_benchmark(
        build_baseline(task, split, dataset),
        task,
        split=split,
        dataset=dataset,
        timestamp=datetime(2024, 5, 1, tzinfo=UTC),
    )

    def resigned(**changes: object) -> BenchmarkResult:
        body = baseline.model_dump(mode="json")
        body.update(changes)
        body.pop("signature", None)
        return BenchmarkResult(**body, signature=content_hash(body))

    board = Leaderboard()
    # Two rows under one split label that disagree on its bytes -> a contested group;
    # a third under a different label -> a second, incomparable group.
    rows = [
        ("lab-a", resigned(split_sha256="a" * 64)),
        ("lab-b", resigned(split_sha256="b" * 64)),
        ("lab-c", resigned(split_version="v2")),
    ]
    for submitter, result in rows:
        board.add(
            Submission(
                submitter=submitter,
                model=result.model,
                results=(result,),
                submitted_at=datetime(2024, 5, 1, tzinfo=UTC),
            )
        )
    return board


def test_the_two_group_fixture_carries_both_prose_blocks(two_group_board: Leaderboard) -> None:
    """The premise. Without both blocks the check below proves nothing."""
    from alleleforge.benchmark.leaderboard import _INCOMPARABLE_NOTE

    text = two_group_board.render_markdown()
    assert _INCOMPARABLE_NOTE in text, "no incomparable-groups note on a two-group board"
    assert any(two_group_board.contested_groups(t) for t in two_group_board.tasks)
    assert "**" in text, "no contested-group warning on a board built to have one"


def test_a_two_group_board_is_still_a_document(two_group_board: Leaderboard) -> None:
    """The same structural claims, on the shape that carries the extra prose."""
    lines = two_group_board.render_markdown().split("\n")
    for i, line in enumerate(lines):
        if i == 0:
            continue
        previous = lines[i - 1]
        if line.startswith("#"):
            assert previous == "", f"the heading {line!r} follows {previous!r}"
        elif line.startswith("|") and not previous.startswith("|"):
            assert previous == "", f"the table starting {line!r} follows {previous!r}"
