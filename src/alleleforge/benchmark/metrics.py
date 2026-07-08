"""CRISPR-Bench metrics — correlation, distribution, ranking, and calibration.

Every function here is **pure Python** with no scientific-stack dependency, so the
benchmark runs in the same lightweight CI environment as the rest of AlleleForge
and produces bit-stable numbers across machines. The metric set mirrors the
specification:

* efficiency (regression): Spearman and Pearson correlation;
* outcome (distribution): KL divergence and top-*k* mode accuracy;
* off-target (classification): AUROC and AUPRC;
* **calibration (ECE) on every task** — the honesty metric. Calibration is
  computed in a kind-appropriate way (interval coverage for regression, binned
  reliability for classification, predicted-mode reliability for distributions),
  but always reported under the single key ``"ece"`` so the leaderboard can rank
  honesty uniformly.

Degenerate inputs (empty, constant) return ``0.0`` rather than ``NaN`` so results
stay JSON-serializable and a uniform-guess baseline scores a clean zero.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

#: Default number of reliability bins for binned calibration (ECE).
DEFAULT_ECE_BINS = 10


def _mean(xs: Sequence[float]) -> float:
    """Return the arithmetic mean of ``xs`` (0.0 for empty)."""
    return sum(xs) / len(xs) if xs else 0.0


def pearson(x: Sequence[float], y: Sequence[float]) -> float:
    """Return the Pearson correlation between ``x`` and ``y``.

    Returns ``0.0`` when the inputs differ in length, are shorter than two
    points, or either series is constant (zero variance).
    """
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    mx, my = _mean(x), _mean(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx <= 0.0 or syy <= 0.0:
        return 0.0
    return sxy / math.sqrt(sxx * syy)


def _rank(xs: Sequence[float]) -> list[float]:
    """Return fractional (tie-averaged) ranks of ``xs``."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # 1-based, averaged over the tie block
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    """Return the Spearman rank correlation between ``x`` and ``y``.

    Computed as the Pearson correlation of tie-averaged ranks; shares the same
    degenerate-input guards as :func:`pearson`.
    """
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    return pearson(_rank(x), _rank(y))


def _normalize(dist: Mapping[str, float]) -> dict[str, float]:
    """Return ``dist`` renormalized to sum to 1 (uniform if total is 0)."""
    total = sum(max(0.0, v) for v in dist.values())
    if total <= 0.0:
        n = len(dist)
        return {k: 1.0 / n for k in dist} if n else {}
    return {k: max(0.0, v) / total for k, v in dist.items()}


def kl_divergence(p: Mapping[str, float], q: Mapping[str, float], *, eps: float = 1e-9) -> float:
    """Return ``KL(p || q)`` in nats over the union of categories.

    Both distributions are renormalized and Laplace-smoothed by ``eps`` so the
    divergence is finite even when ``q`` assigns zero mass to a category ``p``
    supports. ``p`` is the observed/true distribution, ``q`` the predicted one.
    """
    keys = set(p) | set(q)
    if not keys:
        return 0.0
    pn = _normalize({k: p.get(k, 0.0) for k in keys})
    qn = _normalize({k: q.get(k, 0.0) for k in keys})
    total = 0.0
    for k in keys:
        pk = pn[k] + eps
        qk = qn[k] + eps
        total += pk * math.log(pk / qk)
    return max(0.0, total)


def topk_accuracy(
    predicted: Mapping[str, float], observed: Mapping[str, float], *, k: int = 1
) -> float:
    """Return 1.0 if the observed mode is in the predicted top-``k``, else 0.0.

    The "mode" is the highest-mass category of ``observed``; ties broken by
    category name for determinism. Returns ``0.0`` if either side is empty.
    """
    if not predicted or not observed:
        return 0.0
    true_mode = max(sorted(observed), key=lambda c: observed[c])
    top = sorted(predicted, key=lambda c: (-predicted[c], c))[: max(1, k)]
    return 1.0 if true_mode in top else 0.0


def roc_auc(scores: Sequence[float], labels: Sequence[int]) -> float:
    """Return the area under the ROC curve (rank-statistic form).

    ``labels`` are 0/1. Returns ``0.0`` if either class is absent. Ties in
    ``scores`` contribute 0.5, matching the Mann-Whitney U definition.

    Complexity is ``O(pos * neg)`` (a quadratic pairwise sweep), which is fine
    for the fold sizes CRISPR-Bench evaluates but scales poorly if a single fold
    grows to tens of thousands of examples; switch to a tie-averaged rank sum
    (``O(n log n)``) before evaluating folds that large.
    """
    if len(scores) != len(labels):
        return 0.0
    pos = [s for s, y in zip(scores, labels, strict=True) if y == 1]
    neg = [s for s, y in zip(scores, labels, strict=True) if y == 0]
    if not pos or not neg:
        return 0.0
    wins = 0.0
    for sp in pos:
        for sn in neg:
            if sp > sn:
                wins += 1.0
            elif sp == sn:
                wins += 0.5
    return wins / (len(pos) * len(neg))


def pr_auc(scores: Sequence[float], labels: Sequence[int]) -> float:
    """Return the average precision (area under the precision-recall curve).

    Computed as the precision-weighted sum over recall increments as the
    decision threshold sweeps from high to low score. Returns ``0.0`` with no
    positives.

    Tied scores are advanced as a single group: precision and recall are only
    evaluated at each distinct-score boundary, never partway through a run of
    equal scores. This makes the result **order-insensitive** — permuting the
    inputs (or the arbitrary order tied scores happen to sort in) cannot change
    it, which a per-example sweep would allow.
    """
    if len(scores) != len(labels):
        return 0.0
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    total_pos = sum(1 for y in labels if y == 1)
    if total_pos == 0:
        return 0.0
    tp = 0
    fp = 0
    prev_recall = 0.0
    ap = 0.0
    n = len(order)
    i = 0
    while i < n:
        # Consume the whole run of equal scores before evaluating precision/recall.
        j = i
        while j < n:
            if labels[order[j]] == 1:
                tp += 1
            else:
                fp += 1
            if j + 1 < n and scores[order[j + 1]] == scores[order[i]]:
                j += 1
                continue
            break
        recall = tp / total_pos
        precision = tp / (tp + fp)
        ap += precision * (recall - prev_recall)
        prev_recall = recall
        i = j + 1
    return ap


def expected_calibration_error(
    confidences: Sequence[float], correct: Sequence[int], *, n_bins: int = DEFAULT_ECE_BINS
) -> float:
    """Return the binned Expected Calibration Error.

    ``confidences`` are predicted probabilities in ``[0, 1]`` and ``correct`` the
    0/1 indicator of whether that prediction was right. Examples are bucketed
    into ``n_bins`` equal-width confidence bins; ECE is the sample-weighted mean
    gap between bin confidence and bin accuracy. ``0.0`` is perfect calibration.
    """
    if len(confidences) != len(correct) or not confidences:
        return 0.0
    n = len(confidences)
    bins: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for c, y in zip(confidences, correct, strict=True):
        idx = min(n_bins - 1, max(0, int(c * n_bins)))
        bins[idx].append((c, y))
    ece = 0.0
    for bucket in bins:
        if not bucket:
            continue
        conf = _mean([c for c, _ in bucket])
        acc = _mean([float(y) for _, y in bucket])
        ece += (len(bucket) / n) * abs(conf - acc)
    return ece


def interval_calibration_error(
    intervals: Sequence[tuple[float, float]],
    truths: Sequence[float],
    *,
    nominal: float,
) -> float:
    """Return ``|empirical coverage - nominal|`` for predictive intervals.

    For a well-calibrated 80% interval, the truth should fall inside the
    ``(low, high)`` range about 80% of the time; the gap between observed
    coverage and ``nominal`` is the regression analog of ECE. ``0.0`` is perfect.
    """
    if len(intervals) != len(truths) or not intervals:
        return 0.0
    covered = sum(1 for (lo, hi), t in zip(intervals, truths, strict=True) if lo <= t <= hi)
    coverage = covered / len(truths)
    return abs(coverage - nominal)
