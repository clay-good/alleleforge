"""The board grouped by a split *label* and never looked at the split's hash.

`ComparisonGroup` is `(primary_metric, split_version, synthetic)`, and `split_version` is
a string a submitter writes. Two signed submissions can both say `v1` and have been
scored on different bytes — a stale local copy, a regenerated split, a typo — and the
board ranked them against each other while the module's own docstring promises that ranks
never cross a comparison group. `split_sha256` is on every result, precisely so a verifier
can tell, and nothing consulted it.

This is the shape that has been found elsewhere in this project twice: a caller-supplied
*label* trusted where an *identity* was meant. In a cache key it serves one run another's
answer; here it puts an ordering on a table nothing measured, on the artifact most likely
to be screenshotted and quoted.

Grouping still keys on the label, deliberately. The label says what a submitter *intended*
to measure, and silently re-partitioning by hash would produce two identically-captioned
tables and hide the disagreement rather than show it.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from alleleforge.benchmark._canon import content_hash
from alleleforge.benchmark.baseline import build_baseline
from alleleforge.benchmark.leaderboard import Leaderboard, Submission
from alleleforge.benchmark.runner import BenchmarkResult, ModelInfo, run_benchmark
from alleleforge.benchmark.splits import load_split
from alleleforge.benchmark.tasks import get_task

_TS = datetime(2024, 5, 1, tzinfo=UTC)


def _resigned(result: BenchmarkResult, split_sha256: str) -> BenchmarkResult:
    """Return ``result`` scored on a different split, honestly signed.

    Re-signed rather than edited: the signature covers `split_sha256`, so a tampered
    row is rejected at the gate and could never reach a group. The situation this file
    is about is two *legitimate* submissions — two labs, the same `v1` label, different
    bytes — both of which pass every check the board has.
    """
    body = result.model_dump(mode="json")
    body["split_sha256"] = split_sha256
    body.pop("signature", None)
    return BenchmarkResult(**body, signature=content_hash(body))


def _board(*hashes: str) -> Leaderboard:
    task = get_task("cas9-efficiency")
    split, dataset = load_split("cas9-efficiency")
    baseline = run_benchmark(
        build_baseline(task, split, dataset), task, split=split, dataset=dataset, timestamp=_TS
    )
    board = Leaderboard()
    for index, split_hash in enumerate(hashes):
        result = _resigned(baseline, split_hash)
        # The submission's model must match the result's, so the two rows differ by
        # submitter — which is the real scenario: two labs, one split label, two splits.
        board.add(
            Submission(
                submitter=f"lab-{index}",
                model=ModelInfo(**result.model.model_dump()),
                results=(result,),
                submitted_at=_TS,
            )
        )
    return board


def test_a_group_whose_rows_disagree_is_reported(request: pytest.FixtureRequest) -> None:
    board = _board("a" * 64, "b" * 64)
    (task,) = board.tasks
    contested = board.contested_groups(task)
    assert len(contested) == 1, contested
    ((group, hashes),) = contested.items()
    assert len(hashes) == 2, hashes
    assert group.split_version, group


def test_agreeing_rows_are_not_reported() -> None:
    """The check must not fire on the ordinary board, or it becomes noise."""
    board = _board("a" * 64, "a" * 64)
    (task,) = board.tasks
    assert board.contested_groups(task) == {}


@pytest.mark.parametrize("fmt", ["markdown", "html"])
def test_both_renders_say_the_ranking_is_unmeasured(fmt: str) -> None:
    board = _board("a" * 64, "b" * 64)
    text = board.render_markdown() if fmt == "markdown" else board.render_html()
    assert "different split contents" in text, text
    # The consequence, not only the fact: a reader has to know what to do with the order.
    assert "unmeasured" in text, text


@pytest.mark.parametrize("fmt", ["markdown", "html"])
def test_an_agreeing_board_carries_no_such_warning(fmt: str) -> None:
    board = _board("a" * 64, "a" * 64)
    text = board.render_markdown() if fmt == "markdown" else board.render_html()
    assert "different split contents" not in text, text
