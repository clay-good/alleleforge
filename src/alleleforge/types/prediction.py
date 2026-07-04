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
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, ValidationInfo, model_validator

T = TypeVar("T")

#: Module-private capability token. ``calibrated=True`` is honored only when a
#: construction supplies this exact object through the pydantic validation
#: context — which only :meth:`Prediction.calibrated_by` does. A scorer building
#: a ``Prediction`` directly has no way to obtain it, so it cannot self-declare
#: calibration; the flag becomes a guarantee rather than an honor-system field.
_CALIBRATION_TOKEN = object()


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
            interval should be treated with extra caution. An out-of-distribution
            prediction can never also be ``calibrated``.
        calibrated: Whether the interval was post-hoc calibrated. Settable to
            ``True`` only through :meth:`calibrated_by` (a fitted calibrator); a
            direct construction asserting ``calibrated=True`` is coerced to
            ``False``, so the flag is a guarantee, not a self-report.
        notes: Auditable free-form notes attached at construction (e.g. a
            recorded interval repair), stored verbatim in provenance.
    """

    model_config = ConfigDict(frozen=True)

    value: T
    interval: tuple[float, float]
    interval_level: float = 0.80
    method: UncertaintyMethod
    in_distribution: bool = True
    calibrated: bool = False
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _check_interval(self, info: ValidationInfo) -> Prediction[T]:
        """Validate the interval and enforce the tamper-resistant honesty flags.

        Beyond interval ordering, level, and point containment, this coerces
        ``calibrated`` to ``False`` unless the construction was authorized by a
        fitted calibrator (via :meth:`calibrated_by`), and forbids an
        out-of-distribution prediction from also claiming calibration.
        """
        low, high = self.interval
        if low > high:
            raise ValueError(f"interval low {low} exceeds high {high}")
        if not 0.0 < self.interval_level <= 1.0:
            raise ValueError(f"interval_level {self.interval_level} not in (0, 1]")
        value = self.value
        if not isinstance(value, bool) and isinstance(value, (int, float)):
            if not low <= float(value) <= high:
                raise ValueError(f"point estimate {value} lies outside interval {self.interval}")
        if self.calibrated:
            context = info.context or {}
            authorized = context.get("calibration_token") is _CALIBRATION_TOKEN
            if not authorized or not self.in_distribution:
                object.__setattr__(self, "calibrated", False)
        return self

    @classmethod
    def calibrated_by(
        cls,
        *,
        value: T,
        interval: tuple[float, float],
        method: UncertaintyMethod,
        interval_level: float = 0.80,
        in_distribution: bool = True,
        notes: tuple[str, ...] = (),
    ) -> Prediction[T]:
        """Construct a prediction marked ``calibrated=True`` (calibrators only).

        This is the sole authorized path to ``calibrated=True``: a fitted
        conformal/isotonic calibrator calls it to certify that recalibration
        actually happened. An out-of-distribution prediction cannot be
        calibrated, so ``in_distribution=False`` still yields ``calibrated=False``.

        Args:
            value: The point estimate.
            interval: The ``(low, high)`` predictive interval.
            method: The uncertainty method that produced the interval.
            interval_level: The interval's nominal coverage.
            in_distribution: Whether the input is in the training distribution.
            notes: Auditable notes to attach.

        Returns:
            A :class:`Prediction` with ``calibrated=True`` when in-distribution.
        """
        data: dict[str, Any] = {
            "value": value,
            "interval": interval,
            "interval_level": interval_level,
            "method": method,
            "in_distribution": in_distribution,
            "calibrated": True,
            "notes": notes,
        }
        return cls.model_validate(data, context={"calibration_token": _CALIBRATION_TOKEN})

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
        in_distribution = all(p.in_distribution for p in predictions)
        # The combined result inherits calibration only when every input was
        # itself calibrated (each of which could only have earned the flag
        # through the authorized path), so routing through ``calibrated_by`` here
        # propagates a real guarantee rather than forging one.
        if in_distribution and all(p.calibrated for p in predictions):
            return Prediction[float].calibrated_by(
                value=value,
                interval=interval,
                method=UncertaintyMethod.AGREEMENT,
                interval_level=predictions[0].interval_level,
                in_distribution=True,
            )
        return Prediction[float](
            value=value,
            interval=interval,
            interval_level=predictions[0].interval_level,
            method=UncertaintyMethod.AGREEMENT,
            in_distribution=in_distribution,
            calibrated=False,
        )
