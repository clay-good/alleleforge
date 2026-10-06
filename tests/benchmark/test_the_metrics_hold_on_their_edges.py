"""Metric edges a constant-mutation sweep found unpinned.

Eight of 23 survivors in `benchmark/metrics.py` were real; the other fifteen are
equivalent by algebra (centering one side of a covariance suffices; Pearson is invariant
to an affine map of ranks; a loop pass that adds `precision * 0`) or are `strict=True` on
length-checked zips. The real ones:

* the zero-variance guard is `<= 0.0`, and a low-spread correlation is still a number;
  efficiencies in [0, 0.3] routinely have a sum of squares below 0.1;
* a key present in one distribution and absent from the other counts as 0 mass;
* a positive total below 0.1 is still mass to normalize, not "no mass";
* `topk_accuracy` defaults to top-1;
* ECE's top and bottom bins are their own bins, not merged with their neighbours;
* interval coverage includes the endpoints.
"""

from __future__ import annotations

import math

import pytest

from alleleforge.benchmark.metrics import (
    _normalize,
    expected_calibration_error,
    interval_calibration_error,
    kl_divergence,
    pearson,
    topk_accuracy,
)


def test_a_low_spread_correlation_is_a_number() -> None:
    # sum of squares of [0.01, 0.02, 0.03] about its mean is 0.0002.
    assert pearson([0.01, 0.02, 0.03], [0.01, 0.02, 0.03]) == pytest.approx(1.0)


def test_a_missing_key_is_zero_mass_on_either_side() -> None:
    # p puts all mass on "a"; q splits it. KL(p || q) = log 2, whichever side lacks "b".
    assert kl_divergence({"a": 1.0}, {"a": 0.5, "b": 0.5}) == pytest.approx(math.log(2), abs=1e-6)
    assert kl_divergence({"a": 0.5, "b": 0.5}, {"a": 0.5, "b": 0.5}) == pytest.approx(0.0, abs=1e-9)
    assert kl_divergence({"a": 1.0, "b": 0.0}, {"a": 1.0}) == pytest.approx(0.0, abs=1e-6)


def test_a_small_positive_total_is_normalized_not_treated_as_empty() -> None:
    assert _normalize({"a": 0.03, "b": 0.01}) == pytest.approx({"a": 0.75, "b": 0.25})


def test_topk_accuracy_defaults_to_top_one() -> None:
    # The observed mode is the predicted runner-up: a miss at k=1, a hit at k=2.
    predicted = {"a": 0.6, "b": 0.3, "c": 0.1}
    observed = {"b": 1.0}
    assert topk_accuracy(predicted, observed) == 0.0
    assert topk_accuracy(predicted, observed, k=2) == 1.0


@pytest.mark.parametrize(
    ("confidences", "correct", "separate"),
    [
        # Bottom two bins: 0.05 wrong, 0.15 right -> 0.5*0.05 + 0.5*0.85 = 0.45 apart,
        # 0.4 if merged.
        ([0.05, 0.15], [0, 1], 0.45),
        # Top two bins: 0.85 right, 0.95 wrong -> 0.5*0.15 + 0.5*0.95 = 0.55 apart,
        # 0.4 if merged.
        ([0.85, 0.95], [1, 0], 0.55),
    ],
)
def test_the_end_bins_are_their_own_bins(
    confidences: list[float], correct: list[int], separate: float
) -> None:
    assert expected_calibration_error(confidences, correct) == pytest.approx(separate)


def test_a_truth_on_an_interval_endpoint_is_covered() -> None:
    intervals = [(0.2, 0.5), (0.2, 0.5)]
    assert interval_calibration_error(intervals, [0.2, 0.5], nominal=0.8) == pytest.approx(0.2)
