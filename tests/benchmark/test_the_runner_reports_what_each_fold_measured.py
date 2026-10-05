"""The runner's numbers, pinned where the existing fixtures could not tell them apart.

A mutation sweep of `runner.py` found these paths held only by one-sided or symmetric
assertions:

* the generalization gap was asserted `> 0.5`, which `in + held` satisfies as well as
  `in - held`;
* the gap's "one fold has no number" path was only ever reached with *both* folds
  undefined, so `or` and `and` were indistinguishable;
* a classification fold with no number fell through to the generic reason unnoticed;
* `run_benchmark(split=...)` without a dataset was never called;
* the classification ECE's decision threshold and the distribution metrics' means and
  modes had no fixture where getting them wrong moves the number.
"""

from __future__ import annotations

from typing import Any

import pytest

from alleleforge.benchmark.baseline import build_baseline
from alleleforge.benchmark.metrics import expected_calibration_error, kl_divergence
from alleleforge.benchmark.runner import (
    _classification_metrics,
    _distribution_metrics,
    _undefined_reason,
    generalization_gap,
    run_benchmark,
)
from alleleforge.benchmark.splits import load_split
from alleleforge.benchmark.tasks import get_task
from alleleforge.types.prediction import Prediction, UncertaintyMethod
from tests.benchmark.test_generalization import _memorize_fold, _Memorizer


def _p(value: Any) -> Prediction[Any]:
    return Prediction[Any](value=value, interval=(0.0, 1.0), method=UncertaintyMethod.HEURISTIC)


class _ConstantOffFold(_Memorizer):
    """Perfect on the memorized contexts, one constant everywhere else."""

    def score(self, x: Any) -> Prediction[Any]:
        value = self._known.get(x, 0.5)
        return Prediction[float](
            value=value, interval=(value - 0.01, value + 0.01), method=UncertaintyMethod.HEURISTIC
        )


def test_the_gap_is_the_difference_of_the_two_folds() -> None:
    task = get_task("cas9-efficiency")
    split, dataset = load_split("cas9-efficiency")
    scorer = _Memorizer(_memorize_fold(split, dataset, "val"))
    gap = generalization_gap(scorer, task, split=split, dataset=dataset)
    assert gap.higher_is_better is True
    assert gap.held_out != 0.0  # otherwise in - held and in + held agree
    assert gap.gap == pytest.approx(gap.in_context - gap.held_out)


@pytest.mark.parametrize(("memorized", "undefined"), [("test", "val"), ("val", "test")])
def test_one_undefined_fold_is_enough_to_withhold_the_gap(memorized: str, undefined: str) -> None:
    task = get_task("cas9-efficiency")
    split, dataset = load_split("cas9-efficiency")
    scorer = _ConstantOffFold(_memorize_fold(split, dataset, memorized))
    gap = generalization_gap(scorer, task, split=split, dataset=dataset)
    defined = gap.held_out if undefined == "val" else gap.in_context
    assert defined is not None  # the premise: exactly one side is a number
    assert gap.gap is None
    assert gap.undefined_fold == undefined
    assert "constant value" in (gap.undefined_reason or "")


def test_a_classification_fold_states_why_it_has_no_auroc() -> None:
    reason = _undefined_reason(get_task("offtarget-classification"), [_p(0.2), _p(0.9)], [1, 1])
    assert "no negative example" in reason


def test_run_benchmark_resolves_the_dataset_from_the_split() -> None:
    task = get_task("cas9-efficiency")
    split, dataset = load_split("cas9-efficiency")
    scorer = _Memorizer(_memorize_fold(split, dataset, "test"))
    resolved = run_benchmark(scorer, task, split=split)
    given = run_benchmark(scorer, task, split=split, dataset=dataset)
    assert resolved.primary_value == given.primary_value


def test_classification_ece_decides_0_5_as_positive() -> None:
    # Binary ECE is symmetric: flipping a call maps confidence c to 1 - c and "correct" to
    # "wrong", and |acc - conf| does not move. So the threshold is only visible where two
    # predictions share a bin with *mixed* outcomes. 0.5 and 0.55 share the [0.5, 0.6) bin;
    # both decide positive, one is right: mean confidence 0.525, accuracy 0.5.
    assert expected_calibration_error([0.5], [1]) is not None  # premise: 10 equal bins
    got = _classification_metrics([_p(0.5), _p(0.55)], [1, 0])["ece"]
    assert got == pytest.approx(0.025)


def test_distribution_metrics_average_over_examples_and_compare_modes() -> None:
    predicted = [{"a": 0.7, "b": 0.3}, {"a": 0.4, "b": 0.6}]
    observed = [{"a": 0.2, "b": 0.8}, {"a": 0.1, "b": 0.9}]
    got = _distribution_metrics([_p(d) for d in predicted], observed)
    kls = [kl_divergence(o, p) for o, p in zip(observed, predicted, strict=True)]
    assert got["kl"] == pytest.approx(sum(kls) / 2)
    # Mode "a" (wrong) then mode "b" (right): one hit in two.
    assert got["top1"] == pytest.approx(0.5)
    assert got["ece"] == pytest.approx(expected_calibration_error([0.7, 0.6], [0, 1]))


def test_the_distribution_mode_is_the_most_probable_class() -> None:
    # Three classes, because with two the least-probable class is the mode's complement
    # and ECE cannot tell them apart. Predicted mode "a" at 0.6 against a true mode "b":
    # wrong at 0.6 confidence. The least-probable class would be "c" at 0.1.
    got = _distribution_metrics([_p({"a": 0.6, "b": 0.3, "c": 0.1})], [{"a": 0.1, "b": 0.9}])
    assert got["ece"] == pytest.approx(0.6)


def test_baseline_distribution_kl_is_a_mean_not_a_sum() -> None:
    # Over a real fold of many examples the mean and the sum are far apart.
    task = get_task("cas9-outcome")
    split, dataset = load_split("cas9-outcome")
    result = run_benchmark(build_baseline(task, split, dataset), task, split=split, dataset=dataset)
    assert result.n_test > 2
    assert 0.0 <= result.metrics["top1"] <= 1.0
