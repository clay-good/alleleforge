"""The baseline every leaderboard entry is compared against, by value.

`build_baseline` fits the reference scorer to a task's train fold, and its output is the
reference point for the whole board: a submitted model's result means "better or worse than
this". Mutation testing left 16 of 23 mutants alive in that module, clustered entirely in the
fitted numbers -- the train-fold mean, the interval's endpoints, the widening applied to a
constant fold, the final clamp, the distribution marginal, and the classification heuristic's
two saturation points. Every one of them was reachable; none had a value test.

The tests here build a synthetic three-example fold whose answers are arithmetic anyone can
check, so a wrong baseline moves a number rather than only a shape. Labels are chosen so the
mean is **0.4** and not 0.5, because 0.5 is the value the empty-fold fallback returns.
"""

from __future__ import annotations

import pytest

from alleleforge.benchmark.baseline import _MAX_MISMATCH, build_baseline
from alleleforge.benchmark.datasets import BenchmarkDataset
from alleleforge.benchmark.splits import Split
from alleleforge.benchmark.tasks import Example, Task, TaskKind

_SPACER = {"spacer": "A" * 20}


def _fitted(labels: list[object], kind: TaskKind) -> object:
    """Return the baseline fitted to ``labels`` as the whole train fold."""
    examples = tuple(
        Example(example_id=f"e{i}", inputs=_SPACER, label=v) for i, v in enumerate(labels)
    )
    dataset = BenchmarkDataset(
        name="synth",
        version="1",
        examples=examples,
        citation="test fixture",
        license="MIT",
        redistributable=True,
        synthetic=True,
    )
    split = Split(
        task="t",
        dataset="synth",
        dataset_sha256="0" * 64,
        split_sha256="0" * 64,
        split_version="1",
        rationale="a synthetic fold with hand-computable answers",
        train=tuple(f"e{i}" for i in range(len(labels))),
        val=(),
        test=(),
    )
    task = Task(
        name="t",
        kind=kind,
        dataset="synth",
        input_key="spacer",
        metrics=("spearman",),
        description="d",
        chemistry=None,
    )
    return build_baseline(task, split, dataset)


def test_the_regression_baseline_predicts_the_train_fold_mean() -> None:
    """(0.2 + 0.3 + 0.7) / 3 = 0.4, over the observed range [0.2, 0.7]."""
    prediction = _fitted([0.2, 0.3, 0.7], TaskKind.REGRESSION).score(_SPACER)  # type: ignore[attr-defined]
    assert prediction.value == pytest.approx(0.4)
    assert prediction.interval == pytest.approx((0.2, 0.7))


def test_a_constant_fold_is_widened_rather_than_given_a_zero_width_interval() -> None:
    """Every label 0.5: the range has no width, so it is padded to [0.4, 0.6].

    A zero-width interval is a claim of certainty, and this baseline's whole documented
    character is that it predicts one constant and knows nothing -- which is why its rank
    correlation is reported as undefined rather than as a number. The padding is reachable
    only when the fold really is constant, so no ordinary fixture measures it.
    """
    prediction = _fitted([0.5, 0.5, 0.5], TaskKind.REGRESSION).score(_SPACER)  # type: ignore[attr-defined]
    assert prediction.interval == pytest.approx((0.4, 0.6))
    assert prediction.interval[0] < prediction.interval[1], "an interval must have width"
    assert prediction.value == pytest.approx(0.5)


def test_the_predicted_mean_stays_inside_the_interval_it_reports() -> None:
    """The clamp is the invariant, not the arithmetic: a point estimate outside its own
    interval is incoherent, and swapping the two bounds returns a bound instead of the mean.
    """
    for labels in ([0.2, 0.3, 0.7], [0.5, 0.5, 0.5], [0.0, 1.0], [0.9, 0.95]):
        prediction = _fitted(list(labels), TaskKind.REGRESSION).score(_SPACER)  # type: ignore[attr-defined]
        lo, hi = prediction.interval
        assert lo <= prediction.value <= hi, (labels, prediction.value, prediction.interval)


def test_the_distribution_baseline_is_the_summed_train_marginal() -> None:
    """Masses are accumulated across examples and then normalized, not averaged per example.

    {a: 3, b: 1} and {a: 5} sum to {a: 8, b: 1} over a total of 9, so a = 8/9 and b = 1/9. An
    asymmetric fixture is required: with {a: 3, b: 1} and {a: 1, b: 3} the marginal is
    {0.5, 0.5}, which a subtraction or a multiplication also reaches often enough to hide in.
    """
    value = (
        _fitted(  # type: ignore[attr-defined]
            [{"a": 3.0, "b": 1.0}, {"a": 5.0}], TaskKind.DISTRIBUTION
        )
        .score(None)
        .value
    )
    assert value == pytest.approx({"a": 8 / 9, "b": 1 / 9})
    assert sum(value.values()) == pytest.approx(1.0)


def test_a_fold_with_no_observed_mass_is_an_empty_marginal_not_a_crash() -> None:
    """The `total > 0` guard's own case: nothing to normalize by.

    A distribution label whose masses are all zero is an example that observed nothing, and
    it is what a malformed or filtered dataset produces. Relaxed to `>= 0` the guard admits
    exactly that fold into the division and the whole board run dies on it, which is the one
    input the guard was written for and the only one that distinguishes the two.
    """
    scorer = _fitted([{"a": 0.0, "b": 0.0}], TaskKind.DISTRIBUTION)
    assert scorer.score(None).value == {}  # type: ignore[attr-defined]


def test_the_classification_heuristic_saturates_at_both_ends() -> None:
    """1 - mismatches/6, clamped to [0.01, 0.99]: the clamps and the slope each have a case.

    A perfect match is 0.99 and not 1.0, because the board's metrics must never receive a
    probability of exactly 1; six mismatches or more is 0.01 and not 0.0, for the mirror
    reason. One mismatch is 1 - 1/6 = 5/6, which is the only point that pins the slope --
    at the saturated ends a wrong divisor or a flipped sign is hidden by the clamp.
    """
    scorer = _fitted([0.0], TaskKind.CLASSIFICATION)
    assert scorer.score({"mismatches": 0}).value == pytest.approx(0.99)  # type: ignore[attr-defined]
    assert scorer.score({"mismatches": 1}).value == pytest.approx(5 / 6)  # type: ignore[attr-defined]
    assert scorer.score({"mismatches": _MAX_MISMATCH}).value == pytest.approx(0.01)  # type: ignore[attr-defined]
    assert scorer.score({"mismatches": _MAX_MISMATCH * 2}).value == pytest.approx(0.01)  # type: ignore[attr-defined]
