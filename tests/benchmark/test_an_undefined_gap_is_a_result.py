"""Two sibling commands disagreed about the same fold of the same task.

    $ aforge bench run cas9-efficiency
    NOTE: spearman is UNDEFINED for this run, not zero — the model predicted one
    constant value for every example ... The result is recorded and will not be ranked.
    → exit 0

    $ aforge bench gap cas9-efficiency
    error: primary metric 'spearman' is undefined on the 'val' fold ...
    → exit 2

Exit 2 is this CLI's *usage* code: "you invoked the command wrong". The caller invoked it
exactly right and asked a well-formed question about a task whose reference baseline
predicts the train-fold marginal — a constant, by construction and by its own model card,
on every dataset. Two of the five shipped tasks are in that state permanently, so a user
scripting all five got a usage error on 40% of them.

The metric functions were changed to return `None` rather than `0.0` precisely so an
absence could not be read as a measurement. `generalization_gap` turned that `None` back
into a `ValueError` — and the calibration study then rebuilt the honest row by catching
it, which is the shape that belonged in the library.

The `bench gap` command was also, until this round, the one CLI command no test invoked.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from alleleforge.benchmark.baseline import build_baseline
from alleleforge.benchmark.runner import generalization_gap
from alleleforge.benchmark.splits import load_split
from alleleforge.benchmark.tasks import get_task
from alleleforge.cli.main import ExitCode, app

runner = CliRunner()

#: The two shipped regression tasks: their primary metric is a rank correlation, and the
#: reference baseline is a marginal predictor, so the metric is undefined for it always.
_UNDEFINED = ("cas9-efficiency", "pe-efficiency")
#: A task whose primary metric the baseline *can* produce, so the checks below are not
#: passing because everything is undefined.
_DEFINED = "be-outcome"


def _gap(task: str) -> object:
    task_obj = get_task(task)
    split, dataset = load_split(task, version="v1")
    return generalization_gap(
        build_baseline(task_obj, split, dataset), task_obj, split=split, dataset=dataset
    )


@pytest.mark.parametrize("task", _UNDEFINED)
def test_the_library_returns_the_absence_rather_than_raising(task: str) -> None:
    gap = _gap(task)
    assert gap.gap is None  # type: ignore[attr-defined]
    assert gap.undefined_fold == "val"  # type: ignore[attr-defined]
    assert "constant" in (gap.undefined_reason or "")  # type: ignore[attr-defined]


def test_a_measurable_gap_is_still_a_number() -> None:
    """The floor: without this the assertions above pass on a function that always None."""
    gap = _gap(_DEFINED)
    assert isinstance(gap.gap, float)  # type: ignore[attr-defined]
    assert gap.undefined_reason is None  # type: ignore[attr-defined]


@pytest.mark.parametrize("task", _UNDEFINED)
def test_the_command_reports_it_as_a_result_not_a_usage_error(task: str) -> None:
    result = runner.invoke(app, ["bench", "gap", task])
    assert result.exit_code == 0, result.output + result.stderr
    output = result.output + result.stderr
    assert "gap=undefined" in output, output
    assert "UNDEFINED" in output and "constant" in output, output
    # And why no other invocation would help: it is a property of the baseline.
    assert "by construction" in output, output


def test_the_json_carries_the_absence_and_its_reason() -> None:
    result = runner.invoke(app, ["bench", "gap", "cas9-efficiency", "--json"])
    assert result.exit_code == 0, result.output + result.stderr
    payload = json.loads(result.stdout)
    assert payload["gap"] is None
    assert payload["undefined_fold"] == "val"
    assert payload["undefined_reason"]


def test_a_measurable_gap_still_prints_both_folds_and_the_sign() -> None:
    result = runner.invoke(app, ["bench", "gap", _DEFINED])
    assert result.exit_code == 0, result.output + result.stderr
    assert "-> gap=" in result.stdout
    assert "positive = worse on the held-out context" in result.stdout


def test_an_unknown_fold_is_still_a_usage_error() -> None:
    """The exit code the degenerate fold was borrowing: a real caller mistake."""
    result = runner.invoke(app, ["bench", "gap", _DEFINED, "--in-context-fold", "nope"])
    assert result.exit_code == ExitCode.USAGE
    assert "unknown fold" in (result.output + result.stderr)


def test_the_synthetic_caveat_survives_an_undefined_gap() -> None:
    """A NOTE added must not displace the one that was already there."""
    result = runner.invoke(app, ["bench", "gap", "cas9-efficiency"])
    assert "SYNTHETIC" in (result.output + result.stderr)
