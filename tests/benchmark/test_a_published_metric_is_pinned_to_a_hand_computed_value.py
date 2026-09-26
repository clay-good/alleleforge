"""Every leaderboard number, against an answer derived outside the implementation.

`benchmark/metrics.py` was thoroughly tested in *shape*: a perfect correlation is 1.0, a
reversed one -1.0, a degenerate fold is `None`, a confidently-wrong model scores 1.0. Those
are the cases where the arithmetic cannot be wrong — 1.0 comes out of a perfect correlation
however the ranks are averaged, and a fixture whose every confidence is 1.0 puts every
example in one bin, so the binning never runs. Mutation testing found nineteen survivors
concentrated in exactly the parts no shape test reaches: tie-averaged ranks, the two-point
boundary, the positive-label test in the AUC reason, distribution renormalization and its
epsilon, and the ECE bin index.

Each value below is computed by hand in its comment and compared against the
implementation, so the test fails if the arithmetic changes even where the shape does not.
"""

from __future__ import annotations

import math

import pytest

from alleleforge.benchmark.metrics import (
    correlation_undefined_reason,
    expected_calibration_error,
    kl_divergence,
    pearson,
    pr_auc,
    roc_auc,
    roc_auc_undefined_reason,
    spearman,
    topk_accuracy,
)


def test_two_points_are_enough_for_a_correlation() -> None:
    """The guard is `< 2`, so a two-example fold is measurable, not undefined.

    One off-by-one there reports "this fold has at least two examples" folds as
    unmeasurable, and the study prints an undefined-reason row for a number it had.
    """
    assert pearson([1.0, 2.0], [3.0, 7.0]) == 1.0
    assert spearman([1.0, 2.0], [3.0, 7.0]) == 1.0
    # The reason function carries its own copy of the same guard, and a reason arriving
    # beside a number is the contradiction the paired test exists to prevent.
    assert correlation_undefined_reason([1.0, 2.0], [3.0, 7.0]) is None
    assert pearson([1.0], [3.0]) is None, "one point really is undefined"
    assert correlation_undefined_reason([1.0], [3.0]) is not None


def test_pearson_matches_a_hand_computed_value() -> None:
    """x=[1,2,3,4], y=[2,4,5,4]: mx=2.5, my=3.75.

    sxy = (-1.5)(-1.75) + (-0.5)(0.25) + (0.5)(1.25) + (1.5)(0.25) = 3.5
    sxx = 2.25 + 0.25 + 0.25 + 2.25 = 5.0
    syy = 3.0625 + 0.0625 + 1.5625 + 0.0625 = 4.75
    r   = 3.5 / sqrt(5.0 * 4.75) = 3.5 / sqrt(23.75)
    """
    assert pearson([1, 2, 3, 4], [2, 4, 5, 4]) == pytest.approx(3.5 / math.sqrt(23.75))


def test_spearman_averages_a_tie_block_that_is_not_symmetric() -> None:
    """The existing tie check uses `x == y`, where every ranking scheme gives 1.0.

    Here only `x` has the tie. x=[1,2,2,3] gets tie-averaged ranks [1, 2.5, 2.5, 4]
    (the two-element block spans ranks 2 and 3, averaging to 2.5); y=[10,20,30,40]
    gets [1,2,3,4]. Pearson of those, with both means 2.5:

    sxy = (-1.5)(-1.5) + 0 + 0 + (1.5)(1.5) = 4.5
    sxx = 2.25 + 0 + 0 + 2.25 = 4.5;  syy = 2.25 + 0.25 + 0.25 + 2.25 = 5.0
    rho = 4.5 / sqrt(4.5 * 5.0) = 4.5 / sqrt(22.5)

    Any other tie convention -- first-seen ranks, dense ranks, a mis-centred average --
    lands somewhere else, and none of them is 1.0, so a symmetric fixture cannot tell.
    """
    rho = spearman([1, 2, 2, 3], [10, 20, 30, 40])
    assert rho == pytest.approx(4.5 / math.sqrt(22.5))
    assert rho != 1.0, "the tie costs the correlation; a scheme reporting 1.0 lost it"

    # The tie leads, because the run is detected by looking *forward* from its start.
    # A scheme comparing backwards instead groups the wrong pair, and for a tie in the
    # middle the mis-grouped ranks happen to sum to the same correlation -- so the
    # fixture above cannot see it and this one, with the same expected value, can.
    assert spearman([1, 1, 2, 3], [10, 20, 30, 40]) == pytest.approx(4.5 / math.sqrt(22.5))


def test_roc_auc_matches_the_mann_whitney_count() -> None:
    """scores=[0.1,0.4,0.35,0.8], labels=[0,0,1,1]: pos=[0.35,0.8], neg=[0.1,0.4].

    Of the four pos/neg pairs, 0.35>0.1, 0.8>0.1 and 0.8>0.4 are wins and 0.35<0.4 is
    not: 3/4. Not 1.0 and not 0.5, so it separates a correct sweep from a perfect
    fixture and from a coin flip.
    """
    assert roc_auc([0.1, 0.4, 0.35, 0.8], [0, 0, 1, 1]) == 0.75


def test_the_auc_reason_names_the_class_that_is_actually_missing() -> None:
    """A fold of all-positives is missing its *negatives*, and vice versa.

    The reason counts positives with `y == 1`; testing the other class instead swaps
    the two sentences, and each on its own reads perfectly plausible -- so the reader
    goes looking for the examples they already have.
    """
    all_positive = roc_auc_undefined_reason([0.1, 0.2], [1, 1])
    all_negative = roc_auc_undefined_reason([0.1, 0.2], [0, 0])
    assert all_positive is not None and "no negative example" in all_positive
    assert all_negative is not None and "no positive example" in all_negative


def test_pr_auc_matches_a_hand_computed_average_precision() -> None:
    """scores=[0.8,0.4,0.35,0.1], labels=[1,0,1,0], two positives.

    Descending, precision is evaluated at each recall step:
    0.80 -> tp=1 fp=0, recall 0.5, precision 1.0   -> += 1.0 * 0.5   = 0.5
    0.40 -> tp=1 fp=1, recall 0.5, precision 0.5   -> += 0.5 * 0.0   = 0.0
    0.35 -> tp=2 fp=1, recall 1.0, precision 2/3   -> += 2/3 * 0.5   = 1/3
    0.10 -> recall unchanged                        -> += 0.0
    AP = 5/6.
    """
    assert pr_auc([0.8, 0.4, 0.35, 0.1], [1, 0, 1, 0]) == pytest.approx(5 / 6)

    # Two examples share a score in the *middle* of the ranking, so the run must be
    # consumed as one point: one positive and one negative at 0.5 give precision 2/3 at
    # full recall. Scored separately the positive is credited before the negative and AP
    # reaches a perfect 1.0 -- the flattering direction. A fixture where *every* score
    # ties cannot separate the two, because then the whole list is one run either way.
    assert pr_auc([0.9, 0.5, 0.5, 0.1], [1, 1, 0, 0]) == pytest.approx(5 / 6)


def test_ece_is_binned_and_not_one_global_gap() -> None:
    """Confidences 0.1 and 0.9 with correctness 1 and 0 land in different bins.

    Bin 1 holds (0.1, correct): gap |0.1 - 1.0| = 0.9. Bin 9 holds (0.9, wrong):
    gap |0.9 - 0.0| = 0.9. Weighted equally, ECE = 0.9 -- a badly calibrated model.
    Collapse the bin index and the same data reads `|mean(conf) - mean(acc)|` =
    |0.5 - 0.5| = **0.0**, perfect calibration, which is the direction that wins the
    leaderboard's calibration tie-break. Every existing ECE fixture has one bin, where
    the two answers coincide.
    """
    assert expected_calibration_error([0.1, 0.9], [1, 0]) == pytest.approx(0.9)


def test_kl_renormalizes_inputs_that_do_not_sum_to_one() -> None:
    """Counts, not probabilities: p=[3,1] -> [0.75,0.25], q=[1,1] -> [0.5,0.5].

    KL = 0.75*ln(1.5) + 0.25*ln(0.5) = 0.30437 - 0.17329 = 0.13108 nats (the epsilon
    smoothing moves the last digits). A fixture whose masses already sum to 1 divides
    by 1.0, so the renormalization is an identity and cannot be measured there.
    """
    assert kl_divergence({"a": 3.0, "b": 1.0}, {"a": 1.0, "b": 1.0}) == pytest.approx(
        0.75 * math.log(1.5) + 0.25 * math.log(0.5), rel=1e-6
    )


def test_kl_stays_finite_when_the_prediction_gives_a_category_no_mass() -> None:
    """q is all-zero, so it renormalizes to uniform; p keeps all mass on one category.

    KL = 1*ln(1/0.5) = ln 2. This is the case the epsilon exists for: without a
    *positive* smoothing term one side reaches `log` of a non-positive number and the
    metric raises instead of scoring. An all-zero prediction is what a scorer that
    expressed no belief emits, so it is the input the guard was written for.
    """
    assert kl_divergence({"a": 1.0, "b": 0.0}, {"a": 0.0, "b": 0.0}) == pytest.approx(
        math.log(2), rel=1e-6
    )

    # The case the docstring actually names: `q` has mass, just none on a category `p`
    # supports, so it does *not* fall back to uniform and one smoothed term really is
    # `eps`. KL = 0.5*ln(0.5/1) + 0.5*ln(0.5/eps) -- large, and above all finite.
    penalized = kl_divergence({"a": 0.5, "b": 0.5}, {"a": 1.0, "b": 0.0})
    assert math.isfinite(penalized)
    assert penalized == pytest.approx(0.5 * math.log(0.5) + 0.5 * math.log(0.5 / 1e-9), rel=1e-6)


def test_topk_accuracy_is_zero_for_an_empty_side_rather_than_raising() -> None:
    """Either side empty is a miss, not an error -- and `observed` empty has no mode.

    The guard is `not predicted or not observed`; requiring *both* to be empty lets a
    one-sided call through to `max()` over an empty sequence, so a fold containing one
    example with no observed distribution takes the whole run down.
    """
    assert topk_accuracy({}, {"a": 1.0}) == 0.0
    assert topk_accuracy({"a": 1.0}, {}) == 0.0
    assert topk_accuracy({}, {}) == 0.0
