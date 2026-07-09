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


def test_pearson_degenerate_returns_zero() -> None:
    assert pearson([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) == 0.0  # constant x
    assert pearson([1.0], [2.0]) == 0.0  # too few points
    assert pearson([1.0, 2.0], [1.0]) == 0.0  # mismatched length


def test_metrics_treat_nan_as_degenerate_not_perfect() -> None:
    # A NaN slips every `<= 0` / `==` guard (all NaN comparisons are False), so
    # without an explicit check it flowed through: spearman/pr_auc scored corrupt
    # input as a *perfect* 1.0 and pearson returned a non-JSON-serializable NaN —
    # inverting the module's "degenerate inputs return 0.0 rather than NaN, so
    # results stay JSON-serializable" contract. Reachable via a NaN label.
    nan = float("nan")
    assert pearson([1.0, 2.0, nan], [1.0, 2.0, 3.0]) == 0.0
    assert spearman([1.0, 2.0, nan], [1.0, 2.0, 3.0]) == 0.0  # was 1.0 (perfect!)
    assert pr_auc([nan, 0.1, 0.9], [1, 0, 1]) == 0.0  # was 1.0 (perfect!)
    assert roc_auc([nan, 0.1, 0.9], [1, 0, 1]) == 0.0
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
    assert spearman([1.0, 2.0, inf], [1.0, 2.0, 3.0]) == 0.0  # was 1.0 (perfect!)
    assert pearson([1.0, 2.0, inf], [1.0, 2.0, 3.0]) == 0.0  # was NaN
    assert roc_auc([inf, 0.1, 0.2], [1, 0, 0]) == 0.0  # was 1.0 (perfect!)
    assert pr_auc([inf, 0.1, 0.2], [1, 0, 0]) == 0.0  # was 1.0 (perfect!)
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


def test_roc_auc_single_class_returns_zero() -> None:
    assert roc_auc([0.9, 0.8], [1, 1]) == 0.0


def test_pr_auc_perfect() -> None:
    assert pr_auc([0.9, 0.8, 0.2, 0.1], [1, 1, 0, 0]) == 1.0


def test_pr_auc_no_positives_is_zero() -> None:
    assert pr_auc([0.9, 0.1], [0, 0]) == 0.0


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
