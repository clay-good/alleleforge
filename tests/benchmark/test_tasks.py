"""Task contracts are well-formed and ECE is required everywhere (Phase 14)."""

from __future__ import annotations

import pytest

from alleleforge.benchmark.tasks import TASKS, Example, get_task


def test_five_tasks_defined() -> None:
    assert len(TASKS) == 5
    assert set(TASKS) == {
        "cas9-efficiency",
        "cas9-outcome",
        "be-outcome",
        "pe-efficiency",
        "offtarget-classification",
    }


def test_ece_is_required_on_every_task() -> None:
    for task in TASKS.values():
        assert "ece" in task.metrics
        assert task.primary_metric == task.metrics[0]


def test_get_task_unknown_raises() -> None:
    with pytest.raises(KeyError, match="unknown task"):
        get_task("not-a-task")


def test_example_scorer_input_missing_key() -> None:
    ex = Example(example_id="x", inputs={"context": "ACGT"}, label=0.5)
    assert ex.scorer_input("context") == "ACGT"
    with pytest.raises(KeyError, match="no input"):
        ex.scorer_input("pair")
