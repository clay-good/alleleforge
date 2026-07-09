"""Tests for the uncertainty contract: Prediction[T]."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import BaseModel

from alleleforge.types.edit import AlleleOutcome, EditOutcome
from alleleforge.types.prediction import (
    Prediction,
    UncertaintyMethod,
    trusted_deserialization_context,
)


def _pred(value: float, low: float, high: float, **kw: object) -> Prediction[float]:
    return Prediction[float](
        value=value,
        interval=(low, high),
        method=UncertaintyMethod.ENSEMBLE,
        **kw,  # type: ignore[arg-type]
    )


def test_default_interval_level_is_80pct() -> None:
    assert _pred(0.5, 0.4, 0.6).interval_level == 0.80


def test_interval_must_contain_point() -> None:
    with pytest.raises(ValueError, match="outside interval"):
        _pred(0.9, 0.4, 0.6)


def test_interval_ordering_enforced() -> None:
    with pytest.raises(ValueError, match="exceeds high"):
        _pred(0.5, 0.6, 0.4)


def test_interval_level_range_enforced() -> None:
    with pytest.raises(ValueError, match="not in"):
        Prediction[float](
            value=0.5,
            interval=(0.4, 0.6),
            interval_level=1.5,
            method=UncertaintyMethod.ENSEMBLE,
        )


def test_interval_width() -> None:
    assert _pred(0.5, 0.4, 0.7).interval_width == pytest.approx(0.3)


def test_bool_payload_skips_numeric_containment() -> None:
    # bool is a numeric subtype but is not a meaningful point estimate; the
    # containment check is skipped rather than coercing True -> 1.0.
    p = Prediction[bool](value=True, interval=(0.0, 0.4), method=UncertaintyMethod.HEURISTIC)
    assert p.value is True


def test_non_numeric_payload_skips_containment() -> None:
    eo = EditOutcome(alleles=(AlleleOutcome(allele="ACGT", probability=1.0),))
    p = Prediction[EditOutcome](value=eo, interval=(0.0, 1.0), method=UncertaintyMethod.NONE)
    assert p.value.most_likely.allele == "ACGT"


@given(
    st.floats(min_value=0.0, max_value=1.0),
    st.floats(min_value=0.0, max_value=0.5),
)
def test_prediction_interval_always_contains_point(value: float, pad: float) -> None:
    p = _pred(value, max(0.0, value - pad), min(1.0, value + pad) + pad)
    low, high = p.interval
    assert low <= p.value <= high


def test_combine_mean() -> None:
    a = _pred(0.4, 0.3, 0.5)
    b = _pred(0.6, 0.5, 0.7)
    c = Prediction.combine([a, b], reduce="mean")
    assert c.value == pytest.approx(0.5)
    assert c.interval == pytest.approx((0.4, 0.6))
    assert c.method is UncertaintyMethod.AGREEMENT


def test_combine_sum() -> None:
    a = _pred(0.4, 0.3, 0.5)
    b = _pred(0.6, 0.5, 0.7)
    c = Prediction.combine([a, b], reduce="sum")
    assert c.value == pytest.approx(1.0)
    assert c.interval == pytest.approx((0.8, 1.2))


def test_combine_and_flags() -> None:
    a = _pred(0.4, 0.3, 0.5, calibrated=True, in_distribution=True)
    b = _pred(0.6, 0.5, 0.7, calibrated=False, in_distribution=True)
    c = Prediction.combine([a, b])
    assert c.calibrated is False
    assert c.in_distribution is True


def test_combine_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        Prediction.combine([])


def test_combine_rejects_mixed_levels() -> None:
    a = _pred(0.4, 0.3, 0.5)
    b = Prediction[float](
        value=0.6,
        interval=(0.5, 0.7),
        interval_level=0.9,
        method=UncertaintyMethod.ENSEMBLE,
    )
    with pytest.raises(ValueError, match="mix interval levels"):
        Prediction.combine([a, b])


def test_combine_rejects_unknown_reduce() -> None:
    with pytest.raises(ValueError, match="unknown reduce"):
        Prediction.combine([_pred(0.5, 0.4, 0.6)], reduce="median")


# -- honesty flags are tamper-resistant ---------------------------------------


def test_scorer_cannot_self_declare_calibration() -> None:
    # A direct construction asserting calibration is coerced to False: only a
    # fitted calibrator (via calibrated_by) may set the flag.
    p = _pred(0.5, 0.4, 0.6, calibrated=True)
    assert p.calibrated is False


def test_calibrated_by_is_the_authorized_path() -> None:
    p = Prediction[float].calibrated_by(
        value=0.5, interval=(0.4, 0.6), method=UncertaintyMethod.CONFORMAL
    )
    assert p.calibrated is True


def test_ood_cannot_be_calibrated() -> None:
    # Even the authorized path cannot certify an out-of-distribution prediction.
    p = Prediction[float].calibrated_by(
        value=0.5,
        interval=(0.4, 0.6),
        method=UncertaintyMethod.CONFORMAL,
        in_distribution=False,
    )
    assert p.calibrated is False


def test_combine_propagates_real_calibration() -> None:
    a = Prediction[float].calibrated_by(
        value=0.4, interval=(0.3, 0.5), method=UncertaintyMethod.CONFORMAL
    )
    b = Prediction[float].calibrated_by(
        value=0.6, interval=(0.5, 0.7), method=UncertaintyMethod.CONFORMAL
    )
    assert Prediction.combine([a, b]).calibrated is True


def test_notes_default_empty_and_carry_through() -> None:
    assert _pred(0.5, 0.4, 0.6).notes == ()


# -- trained-vs-heuristic legibility ------------------------------------------


def test_point_from_trained_model_defaults_false() -> None:
    assert _pred(0.5, 0.4, 0.6).point_from_trained_model is False


def test_trained_point_is_distinguishable_from_heuristic() -> None:
    # A trained point estimate often ships with an *uncalibrated* heuristic band,
    # so calibrated/in_distribution/method alone cannot separate it from a fully
    # heuristic prediction. The trained flag makes the distinction without
    # reading provenance.
    heuristic = _pred(0.5, 0.35, 0.65, calibrated=False, in_distribution=True)
    trained = _pred(
        0.5, 0.35, 0.65, calibrated=False, in_distribution=True, point_from_trained_model=True
    )
    assert (heuristic.calibrated, heuristic.in_distribution) == (
        trained.calibrated,
        trained.in_distribution,
    )
    assert heuristic.point_from_trained_model != trained.point_from_trained_model


def test_combine_ands_trained_flag() -> None:
    trained = _pred(0.4, 0.3, 0.5, point_from_trained_model=True)
    also_trained = _pred(0.6, 0.5, 0.7, point_from_trained_model=True)
    heuristic = _pred(0.6, 0.5, 0.7, point_from_trained_model=False)
    assert Prediction.combine([trained, also_trained]).point_from_trained_model is True
    # one heuristic input makes the aggregate no longer purely trained
    assert Prediction.combine([trained, heuristic]).point_from_trained_model is False


# -- calibration survives nesting and a trusted round-trip --------------------


class _Holder(BaseModel):
    """Minimal container that nests a Prediction, like a DesignCandidate does."""

    efficiency: Prediction[float]


def test_nesting_does_not_downgrade_or_mutate_calibration() -> None:
    # Placing a certified prediction inside another model must not silently reset
    # its calibrated flag, and must not mutate the shared frozen instance: the
    # gate runs on raw input, so an already-built Prediction passes through intact.
    p = Prediction[float].calibrated_by(
        value=0.5, interval=(0.4, 0.6), method=UncertaintyMethod.CONFORMAL
    )
    holder = _Holder(efficiency=p)
    assert holder.efficiency.calibrated is True
    assert p.calibrated is True  # original not mutated in place


def test_serialized_output_reports_true_and_round_trips_under_trust() -> None:
    # AlleleForge's own serialized output must be faithfully re-loadable: the JSON
    # says calibrated:true, and re-reading it through the trusted context (used
    # when we load a file we wrote) preserves the flag rather than dropping it.
    p = Prediction[float].calibrated_by(
        value=0.5, interval=(0.4, 0.6), method=UncertaintyMethod.CONFORMAL
    )
    payload = _Holder(efficiency=p).model_dump_json()
    assert '"calibrated":true' in payload
    trusted = _Holder.model_validate_json(payload, context=trusted_deserialization_context())
    assert trusted.efficiency.calibrated is True


def test_untrusted_deserialization_cannot_forge_calibration() -> None:
    # A plain load of arbitrary JSON (no trust token) still coerces calibrated to
    # False, so hand-crafted JSON cannot forge a calibration claim.
    forged = (
        '{"efficiency":{"value":0.5,"interval":[0.4,0.6],"interval_level":0.8,'
        '"method":"conformal","in_distribution":true,"calibrated":true,'
        '"point_from_trained_model":false,"notes":[]}}'
    )
    assert _Holder.model_validate_json(forged).efficiency.calibrated is False


def test_trusted_context_still_cannot_calibrate_out_of_distribution() -> None:
    # The OOD invariant holds even through the trusted path: in_distribution=False
    # can never coexist with calibrated=True.
    ood = (
        '{"value":0.5,"interval":[0.4,0.6],"interval_level":0.8,"method":"conformal",'
        '"in_distribution":false,"calibrated":true,"point_from_trained_model":false,"notes":[]}'
    )
    loaded = Prediction[float].model_validate_json(
        ood, context=trusted_deserialization_context()
    )
    assert loaded.calibrated is False


def test_calibrated_by_preserves_trained_flag() -> None:
    p = Prediction[float].calibrated_by(
        value=0.5,
        interval=(0.4, 0.6),
        method=UncertaintyMethod.CONFORMAL,
        point_from_trained_model=True,
    )
    assert p.calibrated is True
    assert p.point_from_trained_model is True
    p = Prediction[float].calibrated_by(
        value=0.5,
        interval=(0.4, 0.6),
        method=UncertaintyMethod.CONFORMAL,
        notes=("hello",),
    )
    assert p.notes == ("hello",)
