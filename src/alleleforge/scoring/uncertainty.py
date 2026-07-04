"""Calibrated uncertainty: ensembles, evidential heads, quantiles, calibration.

The machinery that turns a model's raw output into a Phase 1
:class:`~alleleforge.types.prediction.Prediction` honoring the uncertainty
contract — a point estimate, a calibrated predictive interval (80% by default),
the method that produced it, an out-of-distribution flag, and a calibrated flag.

Everything here is pure stdlib (``math``/``statistics``) — no numpy or torch — so
the whole substrate runs in CI on a weight-free stub embedder:

* :class:`DeepEnsemble` (the default, N=5) aggregates member predictions into a
  mean and a disagreement-driven interval that **widens on out-of-distribution
  inputs** where members diverge.
* :func:`evidential_prediction` is the single-model fallback (a
  Normal-Inverse-Gamma evidential head splitting aleatoric from epistemic
  variance).
* :func:`quantile_prediction` reads an interval straight off predicted quantiles.
* :class:`IsotonicCalibrator` + :func:`expected_calibration_error` provide
  post-hoc calibration that provably reduces ECE on a miscalibrated set.
* :class:`ConformalCalibrator` + :func:`empirical_coverage` recalibrate predictive
  *intervals* to a target coverage with the finite-sample split-conformal
  guarantee (the regression analog), preserving relative interval shape.
* :class:`OODDetector` flags inputs far from a stored training reference in
  embedding space.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from statistics import NormalDist
from typing import Any

from alleleforge.scoring.backbone import Embedding
from alleleforge.types.prediction import Prediction, UncertaintyMethod

#: Default predictive-interval level (the spec's 80%).
DEFAULT_INTERVAL_LEVEL = 0.80

#: Default ensemble size.
DEFAULT_ENSEMBLE_SIZE = 5

#: Factor by which an out-of-distribution interval's half-widths are inflated so
#: an OOD input can never present a narrow, confident interval (uncertainty
#: contract: OOD widens, never narrows).
OOD_WIDEN_FACTOR = 2.0


def _z(level: float) -> float:
    """Return the two-sided standard-normal z for a coverage ``level``."""
    return NormalDist().inv_cdf((1.0 + level) / 2.0)


def to_prediction(
    value: float,
    interval: tuple[float, float],
    *,
    method: UncertaintyMethod,
    level: float = DEFAULT_INTERVAL_LEVEL,
    in_distribution: bool = True,
    notes: tuple[str, ...] = (),
) -> Prediction[float]:
    """Package a value + interval into a Phase 1 :class:`Prediction`.

    The result is always ``calibrated=False``: only a fitted calibrator may
    certify calibration (see :meth:`Prediction.calibrated_by`). Two honesty
    couplings are applied here so no builder can bypass them:

    * **Interval repair is recorded, not silent.** If the point estimate falls
      outside its own interval (a signal the head is inconsistent), the interval
      is widened to contain it *and* a note recording the repair is attached.
    * **Out-of-distribution widens, never narrows.** When ``in_distribution`` is
      ``False`` the interval half-widths are inflated by :data:`OOD_WIDEN_FACTOR`,
      so an OOD input cannot present a narrow interval even if members agree.
    """
    low, high = interval
    low, high = min(low, high), max(low, high)
    notes = tuple(notes)
    if value < low or value > high:
        low, high = min(low, value), max(high, value)
        notes = (
            *notes,
            f"interval widened to contain point estimate {value:.6g} (inconsistent head)",
        )
    if not in_distribution:
        low = value - (value - low) * OOD_WIDEN_FACTOR
        high = value + (high - value) * OOD_WIDEN_FACTOR
    return Prediction[float](
        value=value,
        interval=(low, high),
        interval_level=level,
        method=method,
        in_distribution=in_distribution,
        calibrated=False,
        notes=notes,
    )


@dataclass(frozen=True)
class EnsembleResult:
    """The per-member outputs of an ensemble for one input."""

    members: tuple[float, ...]

    @property
    def mean(self) -> float:
        """Return the ensemble mean."""
        return statistics.fmean(self.members)

    @property
    def std(self) -> float:
        """Return the member standard deviation (0 for a single member)."""
        return statistics.stdev(self.members) if len(self.members) > 1 else 0.0


class DeepEnsemble:
    """An ensemble of member predictors; disagreement drives the interval."""

    def __init__(self, members: Sequence[Callable[[Any], float]]) -> None:
        """Initialise from member predictors (each ``input -> float``).

        Raises:
            ValueError: If no members are given.
        """
        if not members:
            raise ValueError("a DeepEnsemble needs at least one member")
        self._members = tuple(members)

    @property
    def n_members(self) -> int:
        """Return the number of ensemble members."""
        return len(self._members)

    def predict(self, x: Any) -> EnsembleResult:
        """Return the per-member predictions for input ``x``."""
        return EnsembleResult(members=tuple(m(x) for m in self._members))


def ensemble_prediction(
    result: EnsembleResult,
    *,
    level: float = DEFAULT_INTERVAL_LEVEL,
    in_distribution: bool = True,
    method: UncertaintyMethod = UncertaintyMethod.ENSEMBLE,
) -> Prediction[float]:
    """Build a Gaussian predictive interval from ensemble disagreement.

    The raw ensemble interval is not post-hoc calibrated, so the result is
    ``calibrated=False``. ``method`` lets a caller demote a weight-free ensemble
    (content-hashed noise, not a trained backbone) to
    :attr:`UncertaintyMethod.HEURISTIC` so a heuristic result is distinguishable
    from a trained one without reading provenance.
    """
    half = _z(level) * result.std
    return to_prediction(
        result.mean,
        (result.mean - half, result.mean + half),
        method=method,
        level=level,
        in_distribution=in_distribution,
    )


@dataclass(frozen=True)
class EvidentialParams:
    """Normal-Inverse-Gamma evidential-head parameters (Amini et al. 2020).

    Attributes:
        gamma: Predicted mean.
        nu: Evidence for the mean (``> 0``).
        alpha: Evidence for the variance (``> 1``).
        beta: Scale (``> 0``).
    """

    gamma: float
    nu: float
    alpha: float
    beta: float

    def __post_init__(self) -> None:
        """Validate the NIG parameter ranges."""
        if self.nu <= 0 or self.beta <= 0 or self.alpha <= 1:
            raise ValueError("evidential params require nu>0, beta>0, alpha>1")

    @property
    def aleatoric_variance(self) -> float:
        """Return the data (aleatoric) variance ``beta / (alpha - 1)``."""
        return self.beta / (self.alpha - 1.0)

    @property
    def epistemic_variance(self) -> float:
        """Return the model (epistemic) variance ``beta / (nu (alpha - 1))``."""
        return self.beta / (self.nu * (self.alpha - 1.0))

    @property
    def total_variance(self) -> float:
        """Return the total predictive variance."""
        return self.aleatoric_variance + self.epistemic_variance


def evidential_prediction(
    params: EvidentialParams,
    *,
    level: float = DEFAULT_INTERVAL_LEVEL,
    in_distribution: bool = True,
) -> Prediction[float]:
    """Build a predictive interval from an evidential head's parameters."""
    half = _z(level) * math.sqrt(params.total_variance)
    return to_prediction(
        params.gamma,
        (params.gamma - half, params.gamma + half),
        method=UncertaintyMethod.EVIDENTIAL,
        level=level,
        in_distribution=in_distribution,
    )


def _interp_quantile(quantiles: Mapping[float, float], q: float) -> float:
    """Linearly interpolate the value at quantile ``q`` from a quantile map."""
    points = sorted(quantiles.items())
    if q <= points[0][0]:
        return points[0][1]
    if q >= points[-1][0]:
        return points[-1][1]
    for (q0, v0), (q1, v1) in zip(points, points[1:], strict=False):
        if q0 <= q <= q1:
            frac = (q - q0) / (q1 - q0)
            return v0 + frac * (v1 - v0)
    return points[-1][1]


def quantile_prediction(
    quantiles: Mapping[float, float],
    *,
    level: float = DEFAULT_INTERVAL_LEVEL,
    point: float | None = None,
    in_distribution: bool = True,
) -> Prediction[float]:
    """Build a predictive interval directly from predicted quantiles.

    Args:
        quantiles: A map of quantile (in ``(0, 1)``) to predicted value.
        level: The interval coverage; the ``(1-level)/2`` and ``(1+level)/2``
            quantiles bound the interval.
        point: The point estimate; defaults to the interpolated median.
        in_distribution: Whether the input is in distribution.
    """
    low = _interp_quantile(quantiles, (1.0 - level) / 2.0)
    high = _interp_quantile(quantiles, (1.0 + level) / 2.0)
    value = point if point is not None else _interp_quantile(quantiles, 0.5)
    return to_prediction(
        value,
        (low, high),
        method=UncertaintyMethod.QUANTILE,
        level=level,
        in_distribution=in_distribution,
    )


def _pav(values: Sequence[float]) -> list[float]:
    """Pool-adjacent-violators: nearest non-decreasing fit (unit weights)."""
    blocks: list[list[float]] = []  # [sum, weight, start, end]
    for i, v in enumerate(values):
        blocks.append([v, 1.0, i, i])
        while len(blocks) >= 2 and blocks[-2][0] / blocks[-2][1] >= blocks[-1][0] / blocks[-1][1]:
            s2, w2, _a2, b2 = blocks.pop()
            s1, w1, a1, _b1 = blocks.pop()
            blocks.append([s1 + s2, w1 + w2, a1, b2])
    out = [0.0] * len(values)
    for s, w, a, b in blocks:
        mean = s / w
        for i in range(int(a), int(b) + 1):
            out[i] = mean
    return out


class IsotonicCalibrator:
    """Monotonic post-hoc calibration via pool-adjacent-violators regression."""

    def __init__(self) -> None:
        """Create an unfitted calibrator."""
        self._xs: list[float] = []
        self._ys: list[float] = []

    def fit(self, x: Sequence[float], y: Sequence[float]) -> IsotonicCalibrator:
        """Fit a non-decreasing map from ``x`` (scores) to ``y`` (outcomes).

        Raises:
            ValueError: If ``x`` and ``y`` differ in length or are empty.
        """
        if len(x) != len(y) or not x:
            raise ValueError("fit requires non-empty, equal-length x and y")
        order = sorted(range(len(x)), key=lambda i: x[i])
        xs_sorted = [x[i] for i in order]
        ys_iso = _pav([y[i] for i in order])
        # Collapse duplicate x to the last fitted value, keeping x non-decreasing.
        self._xs, self._ys = [], []
        for xv, yv in zip(xs_sorted, ys_iso, strict=True):
            if self._xs and self._xs[-1] == xv:
                self._ys[-1] = yv
            else:
                self._xs.append(xv)
                self._ys.append(yv)
        return self

    def predict_one(self, x: float) -> float:
        """Return the calibrated value for a single score ``x``."""
        if not self._xs:
            raise ValueError("calibrator is not fitted")
        if x <= self._xs[0]:
            return self._ys[0]
        if x >= self._xs[-1]:
            return self._ys[-1]
        for (x0, y0), (x1, y1) in zip(
            zip(self._xs, self._ys, strict=True),
            zip(self._xs[1:], self._ys[1:], strict=True),
            strict=False,
        ):
            if x0 <= x <= x1:
                frac = (x - x0) / (x1 - x0)
                return y0 + frac * (y1 - y0)
        return self._ys[-1]

    def predict(self, x: Sequence[float]) -> list[float]:
        """Return calibrated values for each score in ``x``."""
        return [self.predict_one(v) for v in x]


def empirical_coverage(predictions: Sequence[Prediction[float]], truths: Sequence[float]) -> float:
    """Return the fraction of truths that fall inside their prediction interval.

    The regression analog of accuracy-vs-confidence: a well-calibrated set at level
    ``L`` covers ``~L`` of its truths. Compare against ``interval_level`` to decide
    whether intervals need :class:`ConformalCalibrator` recalibration.

    Raises:
        ValueError: If the inputs differ in length or are empty.
    """
    if len(predictions) != len(truths) or not predictions:
        raise ValueError("coverage requires non-empty, equal-length inputs")
    hits = sum(
        1 for p, y in zip(predictions, truths, strict=True) if p.interval[0] <= y <= p.interval[1]
    )
    return hits / len(predictions)


class ConformalCalibrator:
    """Split-conformal recalibration of predictive intervals to a target coverage.

    When a scorer's intervals are measured *miscalibrated* — empirical coverage off
    the nominal level (see :func:`empirical_coverage`) — this learns a single
    multiplicative **scale** from a held-out calibration set so the recalibrated
    intervals achieve the requested marginal coverage. That is the finite-sample
    split-conformal guarantee: on exchangeable data, recalibrated intervals cover
    the truth with probability at least ``level``. The scale multiplies each
    interval's half-width, so the model's *relative*, per-example uncertainty shape
    (wider where it is less sure) is preserved — only the global width is corrected
    (normalized/scaled conformal). Recalibrated predictions carry
    :attr:`UncertaintyMethod.CONFORMAL` and ``calibrated=True``.

    Calibration intervals must have positive width (the score normalizes by the
    half-width); widen any degenerate interval before fitting.
    """

    def __init__(self, *, level: float = DEFAULT_INTERVAL_LEVEL) -> None:
        """Create an unfitted calibrator targeting marginal coverage ``level``."""
        if not 0.0 < level < 1.0:
            raise ValueError(f"level must be in (0, 1); got {level}")
        self.level = level
        self._scale: float | None = None

    @property
    def scale(self) -> float:
        """Return the fitted interval-width scale (raises if unfitted)."""
        if self._scale is None:
            raise ValueError("calibrator is not fitted")
        return self._scale

    def fit(
        self, predictions: Sequence[Prediction[float]], truths: Sequence[float]
    ) -> ConformalCalibrator:
        """Learn the conformal scale from a calibration set.

        Args:
            predictions: Held-out calibration predictions (positive-width intervals).
            truths: The observed values for those predictions.

        Raises:
            ValueError: If inputs differ in length / are empty, or any calibration
                interval has non-positive width.
        """
        if len(predictions) != len(truths) or not predictions:
            raise ValueError("fit requires non-empty, equal-length predictions and truths")
        scores: list[float] = []
        for p, y in zip(predictions, truths, strict=True):
            half_width = (p.interval[1] - p.interval[0]) / 2.0
            if half_width <= 0.0:
                raise ValueError(
                    "conformal scaling needs positive-width calibration intervals; "
                    "widen degenerate intervals before fitting"
                )
            scores.append(abs(y - p.value) / half_width)
        scores.sort()
        n = len(scores)
        # Finite-sample split-conformal quantile for coverage `level`: the
        # ceil((n+1)*level)-th smallest normalized residual. When that rank exceeds
        # n (too few points to strictly guarantee), fall back to the largest
        # residual — the most conservative finite scale.
        rank = min(math.ceil((n + 1) * self.level), n)
        self._scale = scores[rank - 1]
        return self

    def calibrate(self, prediction: Prediction[float]) -> Prediction[float]:
        """Return ``prediction`` with its interval scaled to the target coverage.

        As a fitted calibrator this is an authorized producer of
        ``calibrated=True`` (via :meth:`Prediction.calibrated_by`). An
        out-of-distribution prediction still resolves to ``calibrated=False``,
        because the honesty contract forbids calibrating an OOD input.
        """
        scale = self.scale
        half_width = (prediction.interval[1] - prediction.interval[0]) / 2.0
        new_half = scale * half_width
        return Prediction[float].calibrated_by(
            value=prediction.value,
            interval=(prediction.value - new_half, prediction.value + new_half),
            method=UncertaintyMethod.CONFORMAL,
            interval_level=self.level,
            in_distribution=prediction.in_distribution,
        )


def expected_calibration_error(
    confidences: Sequence[float],
    outcomes: Sequence[float],
    *,
    n_bins: int = 10,
) -> float:
    """Return the expected calibration error (ECE) over equal-width bins.

    Args:
        confidences: Predicted probabilities/confidences in ``[0, 1]``.
        outcomes: Observed outcomes in ``{0, 1}`` (or empirical frequencies).
        n_bins: Number of equal-width confidence bins.

    Returns:
        The count-weighted mean absolute gap between bin confidence and bin
        outcome frequency.

    Raises:
        ValueError: If the inputs differ in length or are empty.
    """
    if len(confidences) != len(outcomes) or not confidences:
        raise ValueError("ECE requires non-empty, equal-length inputs")
    n = len(confidences)
    ece = 0.0
    for b in range(n_bins):
        lo, hi = b / n_bins, (b + 1) / n_bins
        idx = [
            i for i, c in enumerate(confidences) if (lo <= c < hi) or (b == n_bins - 1 and c == hi)
        ]
        if not idx:
            continue
        bin_conf = statistics.fmean(confidences[i] for i in idx)
        bin_acc = statistics.fmean(outcomes[i] for i in idx)
        ece += (len(idx) / n) * abs(bin_acc - bin_conf)
    return ece


def _euclidean(a: Embedding, b: Embedding) -> float:
    """Return the Euclidean distance between two equal-length embeddings."""
    return math.sqrt(sum((ai - bi) ** 2 for ai, bi in zip(a, b, strict=True)))


class OODDetector:
    """Flag inputs far from a stored training reference in embedding space."""

    def __init__(
        self,
        reference: Sequence[Embedding],
        *,
        quantile: float = 0.95,
        threshold: float | None = None,
    ) -> None:
        """Store the reference set and fix (or derive) the distance threshold.

        Args:
            reference: Training-set embeddings defining the in-distribution region.
            quantile: When ``threshold`` is ``None``, derive it as this quantile
                of the reference nearest-neighbor distances.
            threshold: An explicit distance threshold (overrides ``quantile``).

        Raises:
            ValueError: If the reference set is empty.
        """
        if not reference:
            raise ValueError("OODDetector needs a non-empty reference set")
        self._reference = [tuple(e) for e in reference]
        self.threshold = threshold if threshold is not None else self._derive_threshold(quantile)

    def _derive_threshold(self, quantile: float) -> float:
        """Return the ``quantile`` of reference nearest-neighbor distances."""
        if len(self._reference) == 1:
            return 0.0
        nn = [
            min(_euclidean(a, b) for j, b in enumerate(self._reference) if i != j)
            for i, a in enumerate(self._reference)
        ]
        nn.sort()
        rank = min(len(nn) - 1, int(math.ceil(quantile * len(nn))) - 1)
        return nn[max(0, rank)]

    def distance(self, embedding: Embedding) -> float:
        """Return the distance to the nearest reference embedding."""
        return min(_euclidean(tuple(embedding), r) for r in self._reference)

    def is_in_distribution(self, embedding: Embedding) -> bool:
        """Return ``True`` if ``embedding`` is within the threshold of the reference."""
        return self.distance(embedding) <= self.threshold
