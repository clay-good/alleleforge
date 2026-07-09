"""The uncertainty contract: a generic, calibrated :class:`Prediction`.

Every numeric efficiency or outcome prediction in AlleleForge is returned as a
:class:`Prediction`, never as a bare float. A prediction carries a point
estimate, a calibrated predictive interval (80% by default), the method that
produced the interval, and honesty flags for whether the point was calibrated
and whether the input was in the model's training distribution.

This module is pure: it imports no genome, model, or I/O code.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, ValidationInfo, model_validator

T = TypeVar("T")

#: Auditable note stamped on a fixed-width heuristic interval so its
#: ``interval_level`` is never read as a *measured* coverage. A constant half-width
#: (e.g. ±0.15) cannot be an 80% predictive interval; the level is a nominal target
#: the band was never calibrated to. Pairs with ``calibrated=False``: a consumer
#: thresholding on ``interval_level`` sees, in the notes, that the coverage is
#: unmeasured until a calibrator certifies it.
NOMINAL_INTERVAL_NOTE = "nominal interval level: fixed heuristic half-width, coverage not measured"

#: Auditable note for a *count-valued* quantity (e.g. an expected number of
#: bystander edits) whose fixed spread is not a probability-coverage band at all —
#: the ``interval_level`` does not apply to it in the usual sense.
COUNT_INTERVAL_NOTE = "count-valued quantity: interval is a nominal spread, not a coverage band"

#: Module-private capability token. ``calibrated=True`` is honored only when a
#: construction supplies this exact object through the pydantic validation
#: context — which only :meth:`Prediction.calibrated_by` and
#: :func:`trusted_deserialization_context` do. A scorer building a ``Prediction``
#: directly has no way to obtain it, so it cannot self-declare calibration; the
#: flag becomes a guarantee rather than an honor-system field.
_CALIBRATION_TOKEN = object()


def trusted_deserialization_context() -> dict[str, Any]:
    """Return the validation context that lets ``calibrated=True`` survive a load.

    A :class:`Prediction`'s ``calibrated`` flag is coerced to ``False`` on any
    construction that does not present the calibration token — including a plain
    ``model_validate`` / ``model_validate_json`` of a stored prediction, which
    would otherwise silently drop the flag and make AlleleForge's own serialized
    output un-round-trippable (the JSON says ``"calibrated":true`` but reloading
    it yields ``False``). Pass this context to the *outermost*
    ``model_validate_json`` / ``model_validate`` call when — and only when — the
    bytes are AlleleForge's own prior serialized output that you trust; pydantic
    propagates it to every nested ``Prediction`` so a calibrated prediction buried
    in a :class:`~alleleforge.types.candidate.RankedMenu` round-trips faithfully.

    The trust is placed on the *source of the bytes*, not on the field value: a
    scorer building a prediction in memory never round-trips itself through this
    path, so the anti-forgery guarantee (a scorer cannot self-declare calibration)
    is unaffected. Feeding untrusted or hand-edited JSON here would honor a forged
    ``calibrated`` claim, so restrict it to files AlleleForge itself wrote. The
    ``in_distribution=False`` guard still fires through this path — an
    out-of-distribution prediction can never load back as calibrated.
    """
    return {"calibration_token": _CALIBRATION_TOKEN}


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
        point_from_trained_model: ``True`` when the point estimate comes from a
            trained model (e.g. Rule Set 3, PRIDICT2, BE-DICT, Lindel) rather than
            a transparent rule-of-thumb baseline. A trained point often ships with
            an *uncalibrated* heuristic interval (``calibrated=False``), which would
            otherwise be byte-identical in the honesty flags to a fully heuristic
            prediction — so this makes "trained point, uncalibrated interval"
            distinguishable from "heuristic point" without reading provenance.
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
    point_from_trained_model: bool = False
    notes: tuple[str, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def _gate_calibration(cls, data: Any, info: ValidationInfo) -> Any:
        """Downgrade an unauthorized ``calibrated=True`` on the *raw* input.

        Coercion happens here, on the incoming mapping of field values, rather
        than by mutating a constructed instance. An already-built
        :class:`Prediction` (passed through by nesting it in another model or by
        re-validating it) is not a mapping, so it flows through untouched — a
        certified prediction is never silently downgraded, nor mutated in place,
        just because it was placed inside a :class:`RankedMenu` or revalidated.

        A ``calibrated=True`` claim on fresh mapping/keyword input is honored only
        when the caller presents the module-private calibration token — which only
        :meth:`calibrated_by` (fresh certification) and
        :func:`trusted_deserialization_context` (loading AlleleForge's own output)
        can supply — and the input is in-distribution. Otherwise the flag is reset
        to ``False``, so a scorer still cannot self-declare calibration and an
        out-of-distribution prediction can never load or construct as calibrated.
        """
        if not isinstance(data, Mapping) or not data.get("calibrated"):
            return data
        context = info.context or {}
        authorized = context.get("calibration_token") is _CALIBRATION_TOKEN
        if not authorized or not data.get("in_distribution", True):
            data = dict(data)
            data["calibrated"] = False
        return data

    @model_validator(mode="after")
    def _check_interval(self) -> Prediction[T]:
        """Validate interval ordering, level, and point containment.

        The honesty-flag gate lives in :meth:`_gate_calibration` (a
        ``before`` validator) so this ``after`` pass never mutates ``self`` —
        keeping the frozen model genuinely immutable and safe to alias.
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
        point_from_trained_model: bool = False,
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
            point_from_trained_model: Whether the point estimate came from a
                trained model (preserved from the pre-calibration prediction).
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
            "point_from_trained_model": point_from_trained_model,
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
        # A combined point rests on a trained model only when *every* input point
        # did; one heuristic input makes the aggregate no longer purely trained.
        from_trained = all(p.point_from_trained_model for p in predictions)
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
                point_from_trained_model=from_trained,
            )
        return Prediction[float](
            value=value,
            interval=interval,
            interval_level=predictions[0].interval_level,
            method=UncertaintyMethod.AGREEMENT,
            in_distribution=in_distribution,
            calibrated=False,
            point_from_trained_model=from_trained,
        )
