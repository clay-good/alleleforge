"""Nothing measured over zero examples is a measurement.

The battery a task reports is a dict of numbers, and a number in it is read as a score —
on a board, in a figure, in a paper table. An empty fold determines none of them, and each
metric used to answer that with whatever its own degenerate-input convention happened to
be: a correlation with `0.0`, an AUROC with `0.0` (the worst possible score on that
metric), an accuracy with `0.0` ("got every one wrong"), a KL with `0.0` (the *best*
possible score, so an evaluation over nothing would have topped the leaderboard).

KL was corrected first, and its comment defended the others: it said KL "is unbounded
above, so it has no pessimistic value to fall back to" while "a correlation or an AUROC of
0.0, an accuracy of 0.0" was an acceptable pessimistic answer. That argument does not
survive contact with a ranked table — those values are ranks, not fillers — and the
correlations and AUCs were corrected in the round before this one.

This is the invariant that makes the correction hold for whatever is added next: over an
empty fold, **every** metric of **every** task kind is `None`. It is checked through
`evaluate_fold`, the shared primitive both the runner and the generalization gap go
through, so a new metric added to any battery is covered the day it appears.
"""

from __future__ import annotations

import pytest

from alleleforge.benchmark import TASKS, build_baseline, evaluate_fold, get_task, load_split
from alleleforge.benchmark.splits import Split


@pytest.mark.parametrize("task_name", sorted(TASKS))
def test_every_metric_is_undefined_on_an_empty_fold(task_name: str) -> None:
    task = get_task(task_name)
    split, dataset = load_split(task_name)
    scorer = build_baseline(task, split, dataset)

    empty = Split(
        task=split.task,
        dataset=split.dataset,
        split_version=split.split_version,
        rationale=split.rationale,
        train=split.train,
        val=split.val,
        test=(),
        dataset_sha256=split.dataset_sha256,
        split_sha256=split.split_sha256,
    )
    metrics = evaluate_fold(scorer, task, empty, dataset, "test")

    assert metrics, "no metrics at all; this check would be vacuous"
    assert set(metrics) >= set(task.metrics), (sorted(metrics), task.metrics)
    undefined = {name: value for name, value in metrics.items() if value is not None}
    assert not undefined, (
        f"{task_name} reported {undefined} over an empty fold. Every one of those is read "
        "as a score somewhere — a rank on the board, a bar on a figure — and nothing was "
        "measured."
    )


def test_a_populated_fold_still_reports_numbers() -> None:
    """The floor: without this the check above would pass on a battery of all-None."""
    task = get_task("cas9-outcome")
    split, dataset = load_split("cas9-outcome")
    metrics = evaluate_fold(build_baseline(task, split, dataset), task, split, dataset, "test")
    assert metrics["kl"] is not None and metrics["top1"] is not None
