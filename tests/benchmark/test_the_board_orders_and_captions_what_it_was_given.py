"""The board's ordering and captions, on fixtures that can tell right from wrong.

A mutation sweep of `leaderboard.py` left six mutants alive, and every one survived for
the same reason: the shipped baseline predicts a constant, so every board in the suite
was made of *ties*. Two rows with one score cannot reveal which way the board sorts, so
flipping a higher-is-better ranking to worst-first left the suite green. That is the
most quoted line on the most screenshotted artifact this project publishes.

Each fixture here is built so the wrong behaviour produces a different board: two
distinct scores, a single comparison group (where the "not comparable" banner must not
appear), a row with no split hash beside one with a hash, a group with nothing ranked.
Rows go through the real gate: re-signed honest submissions, as in
`test_the_board_checks_the_split_it_ranks_on`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from alleleforge.benchmark._canon import content_hash
from alleleforge.benchmark.baseline import build_baseline
from alleleforge.benchmark.leaderboard import _INCOMPARABLE_NOTE, Leaderboard, Submission
from alleleforge.benchmark.runner import BenchmarkResult, ModelInfo, run_benchmark
from alleleforge.benchmark.splits import load_split
from alleleforge.benchmark.tasks import get_task

_TS = datetime(2024, 5, 1, tzinfo=UTC)
#: Ranked on AUROC, which is higher-is-better.
_TASK = "offtarget-classification"


def _baseline() -> BenchmarkResult:
    task = get_task(_TASK)
    split, dataset = load_split(_TASK)
    return run_benchmark(
        build_baseline(task, split, dataset), task, split=split, dataset=dataset, timestamp=_TS
    )


def _resigned(result: BenchmarkResult, **update: Any) -> BenchmarkResult:
    body = result.model_dump(mode="json")
    body.update(update)
    body.pop("signature", None)
    return BenchmarkResult(**body, signature=content_hash(body))


def _board(*rows: tuple[str, dict[str, Any]]) -> Leaderboard:
    base = _baseline()
    board = Leaderboard()
    for submitter, update in rows:
        result = _resigned(base, **update)
        board.add(
            Submission(
                submitter=submitter,
                model=ModelInfo(**result.model.model_dump()),
                results=(result,),
                submitted_at=_TS,
            )
        )
    return board


def test_a_higher_is_better_metric_ranks_the_higher_score_first() -> None:
    # Submitted worst-first, so insertion order cannot pass for a sort.
    board = _board(("lab-low", {"primary_value": 0.6}), ("lab-high", {"primary_value": 0.9}))
    assert [e.submitter for e in board.rankings(_TASK)] == ["lab-high", "lab-low"]
    md = board.render_markdown()
    assert md.index("lab-high") < md.index("lab-low")


def test_the_ood_share_is_the_flagged_count_over_the_fold() -> None:
    board = _board(("lab", {"n_test": 10, "n_out_of_distribution": 9}))
    (entry,) = board.rankings(_TASK)
    assert entry.ood_fraction == 0.9
    assert "90% (9/10)" in board.render_markdown()


def test_a_row_without_a_split_hash_does_not_contest_its_group() -> None:
    # Only one row names a hash. An unhashed row predates the field; it is not
    # evidence of a different split, and must not disclaim its neighbour's rank.
    board = _board(("lab-0", {"split_sha256": "a" * 64}), ("lab-1", {"split_sha256": ""}))
    assert board.contested_groups(_TASK) == {}


def test_one_comparison_group_carries_no_incomparability_banner() -> None:
    board = _board(("lab-0", {}), ("lab-1", {}))
    assert len(board.comparison_groups(_TASK)) == 1
    assert _INCOMPARABLE_NOTE not in board.render_markdown()
    assert _INCOMPARABLE_NOTE not in board.render_html()
    # And two groups do carry it, so the absence above is the threshold, not a typo.
    split_board = _board(("lab-0", {}), ("lab-1", {"split_version": "v-other"}))
    assert _INCOMPARABLE_NOTE in split_board.render_markdown()
    assert _INCOMPARABLE_NOTE in split_board.render_html()


def test_the_no_ranked_placeholder_appears_only_when_nothing_is_ranked() -> None:
    ranked = _board(("lab", {"primary_value": 0.7}))
    assert "_no ranked submission_" not in ranked.render_markdown()
    undefined = _board(
        ("lab", {"primary_value": None, "primary_undefined_reason": "single-class fold"})
    )
    assert "_no ranked submission_" in undefined.render_markdown()
