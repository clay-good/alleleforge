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

Degenerate inputs return ``None`` — **undefined**, not zero. A correlation needs
variance in both series and an AUROC needs both classes, and when the input does not
supply them there is no number to report. Returning ``0.0`` there was not a neutral
placeholder: it is a *rank*. The shipped reference baseline predicts a single constant,
so its Spearman is undefined on every fold, and the harness published `0.0` as a measured
score, ranked it on the leaderboard, and subtracted two of them to state a generalization
gap. On AUROC it is worse than neutral — 0.0 reads as perfectly wrong, where an undefined
one is not a performance claim at all.

`None` is the answer already used for calibration in the same result ("kept distinct from
a genuine 0.0 so an empty run is not scored as perfectly calibrated"); the ranking metrics
now use it too. It stays JSON-serializable, which is what the old contract was protecting.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

#: Default number of reliability bins for binned calibration (ECE).
DEFAULT_ECE_BINS = 10


def _mean(xs: Sequence[float]) -> float:
    """Return the arithmetic mean of ``xs`` (0.0 for empty)."""
    return sum(xs) / len(xs) if xs else 0.0


def _has_nonfinite(*seqs: Sequence[float]) -> bool:
    """Return whether any value in any sequence is non-finite (NaN or ±inf).

    A NaN slips every ``<= 0`` / ``==`` degenerate guard (all NaN comparisons are
    ``False``), and ``±inf`` slips them too: an ``inf`` score sorts as the largest
    value, so ``spearman``/``roc_auc``/``pr_auc`` rank corrupt input as a
    **perfect** 1.0; ``pearson`` returns a non-JSON-serializable ``NaN`` (its
    ``inf - inf`` mean gap is NaN); and ``expected_calibration_error`` *crashes*
    with ``OverflowError`` when it bins ``int(inf * n_bins)``. All three invert this
    module's contract — a degenerate input is answered with ``None``, never a perfect
    score, a ``NaN`` that will not serialize, or a crash — so all must be caught. ``NaN``
    is reachable via a corrupt label; ``inf`` via a scorer whose point estimate overflows
    — the ``Prediction`` contract admits ``value=inf`` with an ``(lo, inf)`` interval.
    """
    return any(not math.isfinite(v) for seq in seqs for v in seq)


def pearson(x: Sequence[float], y: Sequence[float]) -> float | None:
    """Return the Pearson correlation between ``x`` and ``y``, or ``None`` if undefined.

    Undefined — ``None``, not ``0.0`` — when the inputs differ in length, are shorter
    than two points, either series is constant (zero variance), or either contains a
    non-finite value (NaN or ±inf). A correlation with a constant series has a zero
    denominator; there is no number, and reporting one puts an unmeasurable model on a
    ranked board beside measured ones.
    """
    if len(x) != len(y) or len(x) < 2 or _has_nonfinite(x, y):
        return None
    mx, my = _mean(x), _mean(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx <= 0.0 or syy <= 0.0:
        return None
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


def spearman(x: Sequence[float], y: Sequence[float]) -> float | None:
    """Return the Spearman rank correlation between ``x`` and ``y``, or ``None``.

    Computed as the Pearson correlation of tie-averaged ranks; shares the same
    degenerate-input guards as :func:`pearson`, including the constant-series one — a
    model that predicts one value for everything has no rank order to correlate. NaN is
    caught here **before** ranking, because ``_rank`` sorts on NaN (all comparisons
    ``False``) and would otherwise emit finite-but-meaningless ranks that score as a
    perfect 1.0.
    """
    if len(x) != len(y) or len(x) < 2 or _has_nonfinite(x, y):
        return None
    return pearson(_rank(x), _rank(y))


def correlation_undefined_reason(x: Sequence[float], y: Sequence[float]) -> str | None:
    """Return why a correlation over ``x`` and ``y`` is undefined, or ``None``.

    A number's absence is only useful if the reader learns what would have produced one.
    "spearman: undefined" sends someone to the code; "the model predicted one constant
    value for every example, and a rank correlation needs variance in both series" sends
    them to their model.

    Kept beside the metrics rather than merged into them because the metrics must stay
    pure numbers; `test_a_reason_exists_exactly_when_the_metric_does_not` pins the two
    together, so this cannot fall out of step with the guards above.
    """
    if len(x) != len(y):
        return f"the series differ in length ({len(x)} vs {len(y)})"
    if len(x) < 2:
        return f"a correlation needs at least two examples; this fold has {len(x)}"
    if _has_nonfinite(x, y):
        return "a value is NaN or infinite, so the ranks and means are meaningless"
    if len(set(y)) == 1:
        return (
            "the model predicted one constant value for every example, and a "
            "correlation needs variance in both series"
        )
    if len(set(x)) == 1:
        return "the labels are constant on this fold, so there is no order to predict"
    return None


def _shared_auc_reason(scores: Sequence[float], labels: Sequence[int]) -> str | None:
    """Return the reason both AUC metrics share, or ``None``."""
    if len(scores) != len(labels):
        return f"scores and labels differ in length ({len(scores)} vs {len(labels)})"
    if _has_nonfinite(scores):
        return "a score is NaN or infinite, so the ranking is meaningless"
    return None


def roc_auc_undefined_reason(scores: Sequence[float], labels: Sequence[int]) -> str | None:
    """Return why :func:`roc_auc` is undefined for these inputs, or ``None``."""
    shared = _shared_auc_reason(scores, labels)
    if shared is not None:
        return shared
    positives = sum(1 for y in labels if y == 1)
    if positives == 0:
        return "this fold has no positive example, so there is no positive/negative pair"
    if positives == len(labels):
        return "this fold has no negative example, so there is no positive/negative pair"
    return None


def pr_auc_undefined_reason(scores: Sequence[float], labels: Sequence[int]) -> str | None:
    """Return why :func:`pr_auc` is undefined for these inputs, or ``None``.

    Not the same predicate as :func:`roc_auc_undefined_reason`: average precision is an
    average over the *positives*, so a fold with no negatives still has one (it is 1.0),
    while AUROC there has no pair to rank. Writing one reason for both metrics is how
    that difference gets flattened — the paired test caught exactly that.
    """
    shared = _shared_auc_reason(scores, labels)
    if shared is not None:
        return shared
    if not any(y == 1 for y in labels):
        return "this fold has no positive example, so there is nothing to average over"
    return None


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
    # Sort the key union: a bare set iterates in PYTHONHASHSEED-dependent order, so
    # the non-associative float summation below (and the `_normalize` totals, whose
    # dicts are built by comprehension over these keys) would vary run-to-run in the
    # low bits — breaking the "bit-stable across machines" contract this module
    # promises and perturbing the signed benchmark result. Same fix as the Round 9
    # `ensemble_outcome` sorted-allele merge.
    keys = sorted(set(p) | set(q))
    if not keys:
        return 0.0
    # Defense-in-depth: a non-finite mass corrupts `_normalize` to `nan`, and
    # `max(0.0, nan)` is `0.0` — a *perfect* score on this lower-is-better metric,
    # so a broken scorer would top the leaderboard. Return the worst value, not the
    # best; the runner's finite-headline validator then rejects the entry outright
    # rather than crowning it. (The `Prediction` contract already blocks a non-finite
    # distribution mass at construction; this guards a direct raw-dict call.)
    if _has_nonfinite(list(p.values()), list(q.values())):
        return math.inf
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
    category name for determinism.

    Returns ``0.0`` — not ``None`` — if either side is empty, and this is the one place
    in the module where a degenerate input still has a value: top-1 is a per-example
    indicator, and a model that predicted nothing did not get this example right. The
    *fold mean* over zero examples is undefined, and :func:`_distribution_metrics` reports
    that as ``None``; the two are different questions and the answers differ accordingly.
    """
    if not predicted or not observed:
        return 0.0
    true_mode = max(sorted(observed), key=lambda c: observed[c])
    top = sorted(predicted, key=lambda c: (-predicted[c], c))[: max(1, k)]
    return 1.0 if true_mode in top else 0.0


def roc_auc(scores: Sequence[float], labels: Sequence[int]) -> float | None:
    """Return the area under the ROC curve (rank-statistic form).

    ``labels`` are 0/1. Returns ``None`` if either class is absent: AUROC is the
    probability that a positive outranks a negative, and with one class present there is
    no such pair. ``0.0`` was the old answer and is the *worst possible score* on this
    metric, so an unmeasurable fold was published as a perfectly wrong model. Ties in
    ``scores`` contribute 0.5, matching the Mann-Whitney U definition.

    Complexity is ``O(pos * neg)`` (a quadratic pairwise sweep), which is fine
    for the fold sizes CRISPR-Bench evaluates but scales poorly if a single fold
    grows to tens of thousands of examples; switch to a tie-averaged rank sum
    (``O(n log n)``) before evaluating folds that large.
    """
    if len(scores) != len(labels) or _has_nonfinite(scores):
        return None
    pos = [s for s, y in zip(scores, labels, strict=True) if y == 1]
    neg = [s for s, y in zip(scores, labels, strict=True) if y == 0]
    if not pos or not neg:
        return None
    wins = 0.0
    for sp in pos:
        for sn in neg:
            if sp > sn:
                wins += 1.0
            elif sp == sn:
                wins += 0.5
    return wins / (len(pos) * len(neg))


def pr_auc(scores: Sequence[float], labels: Sequence[int]) -> float | None:
    """Return the average precision (area under the precision-recall curve).

    Computed as the precision-weighted sum over recall increments as the
    decision threshold sweeps from high to low score. Returns ``None`` with no
    positives: average precision is an average over the positives, and there is nothing
    to average.

    Tied scores are advanced as a single group: precision and recall are only
    evaluated at each distinct-score boundary, never partway through a run of
    equal scores. This makes the result **order-insensitive** — permuting the
    inputs (or the arbitrary order tied scores happen to sort in) cannot change
    it, which a per-example sweep would allow.
    """
    if len(scores) != len(labels) or _has_nonfinite(scores):
        return None
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    total_pos = sum(1 for y in labels if y == 1)
    if total_pos == 0:
        return None
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
) -> float | None:
    """Return the binned Expected Calibration Error, or ``None`` if undefined.

    ``confidences`` are predicted probabilities in ``[0, 1]`` and ``correct`` the
    0/1 indicator of whether that prediction was right. Examples are bucketed
    into ``n_bins`` equal-width confidence bins; ECE is the sample-weighted mean
    gap between bin confidence and bin accuracy. ``0.0`` is perfect calibration.

    Returns ``None`` — **undefined**, not ``0.0`` — when there are no scorable
    predictions (e.g. a distribution scorer that emits ``{}`` everywhere expresses
    no calibrated belief). Reporting that as ``0.0`` would let a model that made no
    real prediction win the calibration ranking; ``None`` keeps "undefined" and
    "perfectly calibrated" distinct.
    """
    if len(confidences) != len(correct) or not confidences or _has_nonfinite(confidences):
        return None
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
) -> float | None:
    """Return ``|empirical coverage - nominal|`` for intervals, or ``None``.

    For a well-calibrated 80% interval, the truth should fall inside the
    ``(low, high)`` range about 80% of the time; the gap between observed
    coverage and ``nominal`` is the regression analog of ECE. ``0.0`` is perfect;
    ``None`` is **undefined** — no intervals to estimate coverage from — kept
    distinct from ``0.0`` so an empty prediction set is not scored as perfect.
    """
    if len(intervals) != len(truths) or not intervals:
        return None
    covered = sum(1 for (lo, hi), t in zip(intervals, truths, strict=True) if lo <= t <= hi)
    coverage = covered / len(truths)
    return abs(coverage - nominal)
