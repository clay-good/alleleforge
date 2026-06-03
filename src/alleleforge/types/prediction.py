"""The uncertainty contract: a generic, calibrated :class:`Prediction`.

Every numeric efficiency or outcome prediction in AlleleForge is returned as a
:class:`Prediction`, never as a bare float. A prediction carries a point
estimate, a calibrated predictive interval (80% by default), the method that
produced the interval, and honesty flags for whether the point was calibrated
and whether the input was in the model's training distribution.

This module is pure: it imports no genome, model, or I/O code.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, model_validator

T = TypeVar("T")


class UncertaintyMethod(StrEnum):
    """How a prediction's interval was produced.

    The value is stored verbatim in provenance so a result can be audited.
    """

    ENSEMBLE = "ensemble"
    EVIDENTIAL = "evidential"
    QUANTILE = "quantile"
    CONFORMAL = "conformal"
    HEURISTIC = "heuristic"
    AGREEMENT = "agreement"
    NONE = "none"


class Prediction(BaseModel, Generic[T]):
    """A point estimate with a calibrated predictive interval.

    The interval is a closed ``(low, high)`` range at ``interval_level``
    confidence (default 0.80). When ``value`` is numeric it is required to lie
    within the interval; non-numeric payloads (e.g. an outcome distribution)
    skip that check.

    Attributes:
        value: The point estimate. May be numeric or a structured payload.
        interval: The ``(low, high)`` predictive interval bounds.
        interval_level: The interval's nominal coverage in ``(0, 1]``.
        method: The uncertainty method that produced the interval.
        in_distribution: ``False`` flags an out-of-distribution input whose
            interval should be treated with extra caution.
        calibrated: Whether the interval was post-hoc calibrated.
    """

    model_config = ConfigDict(frozen=True)

    value: T
    interval: tuple[float, float]
    interval_level: float = 0.80
    method: UncertaintyMethod
    in_distribution: bool = True
    calibrated: bool = False

    @model_validator(mode="after")
    def _check_interval(self) -> Prediction[T]:
        """Validate interval ordering, level, and point containment."""
        low, high = self.interval
        if low > high:
            raise ValueError(f"interval low {low} exceeds high {high}")
        if not 0.0 < self.interval_level <= 1.0:
            raise ValueError(f"interval_level {self.interval_level} not in (0, 1]")
        value = self.value
        if isinstance(value, bool):
            return self
        if isinstance(value, (int, float)):
            if not low <= float(value) <= high:
                raise ValueError(f"point estimate {value} lies outside interval {self.interval}")
        return self

    @property
    def interval_width(self) -> float:
        """Return the width of the predictive interval."""
        low, high = self.interval
        return high - low

    @staticmethod
    def combine(
        predictions: list[Prediction[float]],
        *,
        reduce: str = "mean",
    ) -> Prediction[float]:
        """Combine independent numeric predictions into one.

        Args:
            predictions: Non-empty list of numeric predictions sharing the same
                ``interval_level``.
            reduce: ``"mean"`` to average point and bounds, or ``"sum"`` to add
                them (interval arithmetic for independent sums).

        Returns:
            A combined :class:`Prediction`. ``calibrated`` and
            ``in_distribution`` are the logical AND across inputs; ``method`` is
            :attr:`UncertaintyMethod.AGREEMENT`.

        Raises:
            ValueError: If ``predictions`` is empty, mixes interval levels, or
                ``reduce`` is unknown.
        """
        if not predictions:
            raise ValueError("cannot combine an empty list of predictions")
        levels = {p.interval_level for p in predictions}
        if len(levels) != 1:
            raise ValueError(f"predictions mix interval levels: {sorted(levels)}")
        values = [float(p.value) for p in predictions]
        lows = [p.interval[0] for p in predictions]
        highs = [p.interval[1] for p in predictions]
        if reduce == "mean":
            n = len(predictions)
            value = sum(values) / n
            interval = (sum(lows) / n, sum(highs) / n)
        elif reduce == "sum":
            value = sum(values)
            interval = (sum(lows), sum(highs))
        else:
            raise ValueError(f"unknown reduce {reduce!r}; use 'mean' or 'sum'")
        return Prediction[float](
            value=value,
            interval=interval,
            interval_level=predictions[0].interval_level,
            method=UncertaintyMethod.AGREEMENT,
            in_distribution=all(p.in_distribution for p in predictions),
            calibrated=all(p.calibrated for p in predictions),
        )
