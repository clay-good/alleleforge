"""Metrics match hand-computed values on tiny fixtures (Phase 14)."""

from __future__ import annotations

import json
import math

import pytest

from alleleforge.benchmark.metrics import (
    expected_calibration_error,
    interval_calibration_error,
    kl_divergence,
    pearson,
    pr_auc,
    roc_auc,
    spearman,
    topk_accuracy,
)


def test_pearson_perfect_positive() -> None:
    assert pearson([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == 1.0


def test_pearson_perfect_negative() -> None:
    assert pearson([1.0, 2.0, 3.0], [3.0, 2.0, 1.0]) == -1.0


def test_pearson_degenerate_is_undefined_not_zero() -> None:
    """`0.0` is not a neutral placeholder on a ranked board; it is a score.

    The shipped reference baseline predicts a single constant, so its correlation is
    undefined on every fold — and the harness published `0.0` as a measured Spearman,
    ranked it, and subtracted two of them to state a generalization gap.
    """
    assert pearson([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) is None  # constant x
    assert pearson([1.0, 2.0, 3.0], [7.0, 7.0, 7.0]) is None  # constant y
    assert pearson([1.0], [2.0]) is None  # too few points
    assert pearson([1.0, 2.0], [1.0]) is None  # mismatched length


def test_metrics_treat_nan_as_degenerate_not_perfect() -> None:
    # A NaN slips every `<= 0` / `==` guard (all NaN comparisons are False), so
    # without an explicit check it flowed through: spearman/pr_auc scored corrupt
    # input as a *perfect* 1.0 and pearson returned a non-JSON-serializable NaN —
    # inverting the module's "degenerate inputs return 0.0 rather than NaN, so
    # results stay JSON-serializable" contract. Reachable via a NaN label.
    nan = float("nan")
    assert pearson([1.0, 2.0, nan], [1.0, 2.0, 3.0]) is None
    assert spearman([1.0, 2.0, nan], [1.0, 2.0, 3.0]) is None  # was 1.0 (perfect!)
    assert pr_auc([nan, 0.1, 0.9], [1, 0, 1]) is None  # was 1.0 (perfect!)
    assert roc_auc([nan, 0.1, 0.9], [1, 0, 1]) is None
    assert expected_calibration_error([nan, 0.5], [1, 0]) is None  # was a crash
    # Every metric now stays JSON-serializable (no NaN escapes).
    json.dumps(
        {
            "pearson": pearson([1.0, 2.0, nan], [1.0, 2.0, 3.0]),
            "pr_auc": pr_auc([nan, 0.1, 0.9], [1, 0, 1]),
        },
        allow_nan=False,
    )


def test_metrics_treat_inf_as_degenerate_not_perfect() -> None:
    # `±inf` is a finite-*ordering* value: it sorts as the largest element and
    # satisfies every `<= 0` / `==` guard, so it slipped the NaN-only check. An inf
    # score then ranked corrupt input as a *perfect* 1.0 (spearman/roc_auc/pr_auc),
    # pearson returned a non-JSON-serializable NaN, and ECE *crashed* on
    # `int(inf * n_bins)`. Reachable: the Prediction contract admits value=inf.
    inf = float("inf")
    assert spearman([1.0, 2.0, inf], [1.0, 2.0, 3.0]) is None  # was 1.0 (perfect!)
    assert pearson([1.0, 2.0, inf], [1.0, 2.0, 3.0]) is None  # was NaN
    assert roc_auc([inf, 0.1, 0.2], [1, 0, 0]) is None  # was 1.0 (perfect!)
    assert pr_auc([inf, 0.1, 0.2], [1, 0, 0]) is None  # was 1.0 (perfect!)
    assert expected_calibration_error([inf, 0.5], [1, 0]) is None  # was an OverflowError crash
    json.dumps({"pearson": pearson([1.0, 2.0, inf], [1.0, 2.0, 3.0])}, allow_nan=False)


def test_spearman_is_monotone_invariant() -> None:
    # A monotone (non-linear) relationship: Spearman == 1, Pearson < 1.
    x = [1.0, 2.0, 3.0, 4.0]
    y = [1.0, 4.0, 9.0, 16.0]
    assert spearman(x, y) == 1.0
    assert pearson(x, y) < 1.0


def test_spearman_handles_ties() -> None:
    # Tie-averaged ranks keep a constant series degenerate, not crashing.
    assert spearman([1.0, 1.0, 2.0], [1.0, 1.0, 2.0]) == 1.0


def test_kl_zero_for_identical_distributions() -> None:
    p = {"a": 0.5, "b": 0.5}
    assert kl_divergence(p, p) < 1e-6


def test_kl_matches_hand_computation() -> None:
    p = {"a": 0.5, "b": 0.5}
    q = {"a": 0.25, "b": 0.75}
    expected = 0.5 * math.log(0.5 / 0.25) + 0.5 * math.log(0.5 / 0.75)
    assert abs(kl_divergence(p, q, eps=0.0) - expected) < 1e-6


def test_kl_empty_is_zero() -> None:
    assert kl_divergence({}, {}) == 0.0


def test_kl_treats_nonfinite_mass_as_worst_not_perfect() -> None:
    # A non-finite predicted mass normalizes to `nan`, and `max(0.0, nan)` is `0.0`
    # — a *perfect* score on this lower-is-better metric, so a broken scorer would
    # top the leaderboard. It must instead be the WORST value (inf), which the
    # runner's finite-headline validator then rejects outright. (R24)
    truth = {"a": 0.5, "b": 0.5}
    assert kl_divergence(truth, {"a": float("inf"), "b": 1.0}) == float("inf")  # was 0.0
    assert kl_divergence(truth, {"a": float("nan"), "b": 1.0}) == float("inf")
    assert kl_divergence({"a": float("inf")}, {"a": 1.0}) == float("inf")


def test_kl_is_byte_stable_across_hash_seeds() -> None:
    # kl_divergence summed floats over a bare `set(p) | set(q)`, whose iteration
    # order is PYTHONHASHSEED-dependent; non-associative float addition then made
    # the low bits vary run-to-run — perturbing the signed benchmark result and
    # breaking the module's "bit-stable across machines" contract. Run the same
    # KL in fresh interpreters under different hash seeds; the repr must be equal.
    import os
    import subprocess
    import sys

    prog = (
        "from alleleforge.benchmark.metrics import kl_divergence;"
        "p={f'allele_{i:03d}':(i%7)+1 for i in range(60)};"
        "q={f'allele_{i:03d}':((i*3)%5)+1 for i in range(60)};"
        "print(repr(kl_divergence(p,q)))"
    )
    outs = {
        subprocess.run(
            [sys.executable, "-c", prog],
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "PYTHONHASHSEED": str(seed)},
        ).stdout.strip()
        for seed in (0, 1, 2, 3, 4)
    }
    assert len(outs) == 1, f"kl_divergence is hash-seed dependent: {outs}"


def test_topk_accuracy() -> None:
    predicted = {"del": 0.6, "ins": 0.3, "wt": 0.1}
    observed = {"del": 0.7, "ins": 0.2, "wt": 0.1}
    assert topk_accuracy(predicted, observed, k=1) == 1.0
    observed_ins = {"del": 0.1, "ins": 0.8, "wt": 0.1}
    assert topk_accuracy(predicted, observed_ins, k=1) == 0.0
    assert topk_accuracy(predicted, observed_ins, k=2) == 1.0
    assert topk_accuracy({}, observed) == 0.0


def test_roc_auc_perfect_separation() -> None:
    scores = [0.9, 0.8, 0.2, 0.1]
    labels = [1, 1, 0, 0]
    assert roc_auc(scores, labels) == 1.0


def test_roc_auc_ties_count_half() -> None:
    # One positive and one negative with equal scores -> AUROC 0.5.
    assert roc_auc([0.5, 0.5], [1, 0]) == 0.5


def test_roc_auc_single_class_is_undefined_not_the_worst_score() -> None:
    """On AUROC, `0.0` is not neutral — it is "perfectly wrong"."""
    assert roc_auc([0.9, 0.8], [1, 1]) is None
    assert roc_auc([0.9, 0.8], [0, 0]) is None


def test_pr_auc_perfect() -> None:
    assert pr_auc([0.9, 0.8, 0.2, 0.1], [1, 1, 0, 0]) == 1.0


def test_pr_auc_no_positives_is_undefined() -> None:
    """Average precision averages over the positives; there are none to average."""
    assert pr_auc([0.9, 0.1], [0, 0]) is None


def test_pr_auc_tied_scores_are_order_insensitive() -> None:
    # Every example shares one score, so the ranking is fully ambiguous. Tie
    # grouping must collapse the whole run to a single precision/recall point,
    # giving the same average precision for every label permutation.
    from itertools import permutations

    results = {
        round(pr_auc([0.5, 0.5, 0.5], list(labels)), 12) for labels in permutations([1, 1, 0])
    }
    assert results == {round(2 / 3, 12)}


def test_ece_perfectly_calibrated_is_zero() -> None:
    # All confidences 1.0 and all correct -> zero gap.
    assert expected_calibration_error([1.0, 1.0, 1.0], [1, 1, 1]) == 0.0


def test_ece_max_miscalibration() -> None:
    # Confidently wrong every time -> ECE == 1.0.
    assert expected_calibration_error([1.0, 1.0], [0, 0]) == 1.0


def test_ece_empty_is_undefined_not_zero() -> None:
    # No scorable predictions -> ECE is undefined (None), NOT a perfect 0.0. A
    # model that expressed no calibrated belief must not be reported as perfectly
    # calibrated (which would win the leaderboard's calibration tie-break).
    assert expected_calibration_error([], []) is None


def test_interval_calibration_error() -> None:
    intervals = [(0.0, 1.0), (0.0, 1.0), (0.0, 0.1), (0.0, 0.1)]
    truths = [0.5, 0.5, 0.5, 0.5]  # first two covered, last two not -> coverage 0.5
    assert interval_calibration_error(intervals, truths, nominal=0.8) == pytest.approx(0.3)
    assert interval_calibration_error([], [], nominal=0.8) is None  # undefined, not 0.0


def test_an_empty_distribution_evaluation_reports_kl_as_undefined() -> None:
    """KL is LOWER_IS_BETTER, so 0.0 is its *best* value, not a neutral one.

    Averaging zero divergences to 0.0 posts a *perfect* score, and `LOWER_IS_BETTER`
    would rank that submission first. `ece`, computed from the same empty inputs,
    already returned None; KL had to too.

    This docstring used to defend the rest of the battery — "every other metric in this
    suite can fail pessimistically toward a bounded worst value — a correlation or an
    AUROC of 0.0, an accuracy of 0.0 — and does so deliberately, so a degenerate
    evaluation cannot flatter itself". Not flattering itself is not the same as being
    honest: on a ranked board those values are ranks, and `0.0` on an AUROC is the worst
    possible *score* rather than a statement that nothing was measured. All of them are
    `None` now, top-1 included, and
    `test_an_empty_fold_measures_nothing.py` holds the whole battery to it.
    """
    from alleleforge.benchmark.leaderboard import LOWER_IS_BETTER
    from alleleforge.benchmark.runner import _distribution_metrics

    assert "kl" in LOWER_IS_BETTER  # the premise: lower wins, so 0.0 is the top
    empty = _distribution_metrics([], [])
    assert empty["kl"] is None
    assert empty["ece"] is None
    assert empty["top1"] is None


def test_a_non_empty_distribution_evaluation_still_reports_a_number() -> None:
    """The fix must not turn every evaluation undefined."""
    from alleleforge.benchmark.runner import _distribution_metrics
    from alleleforge.types.prediction import Prediction, UncertaintyMethod

    prediction = Prediction[dict[str, float]](
        value={"a": 0.7, "b": 0.3},
        interval=(0.0, 1.0),
        method=UncertaintyMethod.HEURISTIC,
    )
    result = _distribution_metrics([prediction], [{"a": 0.7, "b": 0.3}])
    assert isinstance(result["kl"], float)
    assert result["kl"] >= 0.0


@pytest.mark.parametrize(
    "x,y",
    [
        ([1.0, 2.0, 3.0], [3.0, 1.0, 2.0]),  # ordinary
        ([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]),  # constant labels
        ([1.0, 2.0, 3.0], [7.0, 7.0, 7.0]),  # constant predictions
        ([1.0], [2.0]),  # too few
        ([1.0, 2.0], [1.0]),  # mismatched
        ([1.0, 2.0, float("nan")], [1.0, 2.0, 3.0]),
        ([1.0, 2.0, float("inf")], [1.0, 2.0, 3.0]),
    ],
)
def test_a_correlation_reason_exists_exactly_when_the_metric_does_not(
    x: list[float], y: list[float]
) -> None:
    """The reason lives beside the guards rather than inside them; keep them in step.

    A missing number is only useful if the reader learns what would have produced one,
    and a reason that disagrees with the metric is worse than none — it would either
    explain a number that exists or leave an absence unexplained.
    """
    from alleleforge.benchmark.metrics import correlation_undefined_reason

    assert (pearson(x, y) is None) == (correlation_undefined_reason(x, y) is not None)
    assert (spearman(x, y) is None) == (correlation_undefined_reason(x, y) is not None)


@pytest.mark.parametrize(
    "scores,labels",
    [
        ([0.9, 0.1], [1, 0]),  # ordinary
        ([0.9, 0.8], [1, 1]),  # no negatives
        ([0.9, 0.8], [0, 0]),  # no positives
        ([0.9], [1, 0]),  # mismatched
        ([float("nan"), 0.1], [1, 0]),
    ],
)
def test_an_auc_reason_exists_exactly_when_the_metric_does_not(
    scores: list[float], labels: list[int]
) -> None:
    from alleleforge.benchmark.metrics import pr_auc_undefined_reason, roc_auc_undefined_reason

    assert (roc_auc(scores, labels) is None) == (
        roc_auc_undefined_reason(scores, labels) is not None
    )
    # A separate predicate, and this test is why: average precision over a fold with no
    # negatives is defined (1.0) while AUROC there is not, so one shared reason would
    # have claimed an existing number was missing.
    assert (pr_auc(scores, labels) is None) == (pr_auc_undefined_reason(scores, labels) is not None)
