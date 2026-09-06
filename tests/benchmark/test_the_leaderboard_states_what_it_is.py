"""The leaderboard must carry the context a published page needs.

`aforge bench leaderboard --format html --out board.html` writes the artifact most
likely of any this tool produces to be published, linked, screenshotted and quoted —
a ranked table of models. It carried the one thing it most needed, marking every
synthetic split `(synthetic)` and labelling each section a *synthetic stand-in*, and
none of the rest:

    contains 'synthetic'            True
    contains 'not a medical device' False
    contains 'research'             False

No research-use disclaimer, no AlleleForge version, no generation time. A ranked board
of CRISPR models with numbers to four decimal places and nothing saying what produced
it or what it is for.

It is neither a `DesignReport` render nor a cohort summary nor an off-target payload,
so none of the checks that cover those had ever looked at it — the same blind spot
those rounds each found one artifact over. Both renders are covered here, because a
markdown board pasted into an issue travels exactly as far as the HTML one.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from alleleforge.benchmark.baseline import build_baseline
from alleleforge.benchmark.leaderboard import Leaderboard, Submission
from alleleforge.benchmark.runner import run_benchmark
from alleleforge.report.builder import RESEARCH_USE_CORE


def _board(tasks: tuple[str, ...]) -> Leaderboard:
    board = Leaderboard()
    from alleleforge.benchmark.splits import load_split
    from alleleforge.benchmark.tasks import get_task

    results = []
    for name in tasks:
        task = get_task(name)
        split, dataset = load_split(name)
        results.append(
            run_benchmark(build_baseline(task, split, dataset), task, split=split, dataset=dataset)
        )
    by_model: dict[str, list] = {}
    for result in results:
        by_model.setdefault(result.model.name, []).append(result)
    for model_results in by_model.values():
        board.add(
            Submission(
                submitter="local",
                model=model_results[0].model,
                results=tuple(model_results),
                submitted_at=datetime.now(UTC),
            )
        )
    return board


@pytest.fixture
def board() -> Leaderboard:
    return _board(("cas9-efficiency", "pe-efficiency"))


def _renders(board: Leaderboard) -> dict[str, str]:
    return {"markdown": board.render_markdown(), "html": board.render_html()}


def test_the_synthetic_marking_is_still_there(board: Leaderboard) -> None:
    """Guard the part that was already right, before adding to it."""
    for name, text in _renders(board).items():
        assert "synthetic" in text.lower(), name


@pytest.mark.parametrize("render", ["markdown", "html"])
def test_the_disclaimer_is_present(board: Leaderboard, render: str) -> None:
    text = _renders(board)[render]
    assert RESEARCH_USE_CORE in text


@pytest.mark.parametrize("render", ["markdown", "html"])
def test_the_version_is_named(board: Leaderboard, render: str) -> None:
    """A board with no version cannot be compared to the board published next month."""
    from alleleforge._version import __version__

    assert __version__ in _renders(board)[render]


@pytest.mark.parametrize("render", ["markdown", "html"])
def test_an_empty_board_still_says_what_it_is(board: Leaderboard, render: str) -> None:
    """The no-submissions page is the one most likely to be published first."""
    empty = Leaderboard()
    text = _renders(empty)[render]
    assert RESEARCH_USE_CORE in text


def test_the_html_escapes_the_disclaimer_once(board: Leaderboard) -> None:
    """A double-escaped disclaimer would render as literal entities on the page."""
    assert "&amp;amp;" not in board.render_html()


@pytest.mark.parametrize("render", ["markdown", "html"])
def test_the_disclaimer_describes_a_leaderboard(board: Leaderboard, render: str) -> None:
    """Reusing the design report's sentence verbatim imports a wrong clause.

    `RESEARCH_USE_DISCLAIMER` says "the candidates below are ranked ... hypotheses",
    which is right on a design report and false on a board of models: there are no
    candidates below it. A caveat that does not describe the thing it is attached to
    is noise, and the neutral core plus a board-specific sentence is the fix.
    """
    text = _renders(board)[render]
    assert "The candidates below" not in text
    assert "benchmark metrics on frozen splits" in text


def test_the_markdown_prose_is_not_table_escaped(board: Leaderboard) -> None:
    """`_md_cell` exists for attacker-controlled cells, not for this module's prose.

    Applied to it, "validated (e.g. GUIDE-seq)" renders as "validated \\(e.g. ...\\)".
    """
    markdown = board.render_markdown()
    notes = [line for line in markdown.splitlines() if line.startswith("> ")]
    assert notes
    assert not any("\\(" in line or "\\." in line for line in notes), notes
