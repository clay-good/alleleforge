"""`calibrated=True` is a guarantee, and junk input must not be a way around it.

`Prediction.calibrated` is the one flag in this library that cannot be self-declared: a
scorer asserting it is coerced to `False`, and only `calibrated_by` (a fitted calibrator
certifying fresh work) or `trusted_deserialization_context` (loading AlleleForge's own
output) can set it. The before-validator enforces two conditions together — an authorized
token *and* an in-distribution input.

The second condition was pinned for a well-formed `in_distribution=False` and not for an
`in_distribution` that is not a boolean at all. That path is uncovered, and it is the one
where the gate has to decide what to do with a value it cannot read: the code reads it
through a `TypeAdapter(bool)` and, on failure, treats the input as out-of-distribution so
calibration is not preserved on something it could not interpret.

Today that branch is belt-and-braces — the field validator rejects every
non-bool-coercible value, so validation fails whatever the gate decided, and no object is
produced to inspect. Its comment says as much. So these tests deliberately assert the
**guarantee** rather than the branch: whatever the shape of the junk, the result is never
a calibrated prediction. That statement survives the branch being belt-and-braces today
and survives the field validator being relaxed later, which is exactly when the branch
would start carrying weight on its own.

Found as an uncovered-line gap in the calibration gate — the machinery this project
relies on to keep its own honesty claims true, and where three of four defects landed the
last time it was audited.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from alleleforge.types.prediction import (
    Prediction,
    UncertaintyMethod,
    trusted_deserialization_context,
)

#: Values a caller might put in `in_distribution` that are not booleans. `3.7` matters
#: because pydantic's lax bool *does* accept `0.0` and `1.0`, so a float is only junk
#: when it is neither.
_JUNK: list[Any] = ["junk", [], {}, 3.7, None, object(), (True,)]


def _payload(in_distribution: Any) -> dict[str, Any]:
    return {
        "value": 0.5,
        "interval": (0.4, 0.6),
        "interval_level": 0.8,
        "method": UncertaintyMethod.HEURISTIC.value,
        "calibrated": True,
        "in_distribution": in_distribution,
    }


@pytest.mark.parametrize("junk", _JUNK)
def test_junk_in_distribution_never_yields_a_calibrated_prediction(junk: Any) -> None:
    """Either it refuses, or it loads uncalibrated. Never calibrated.

    Asserted as a disjunction on purpose. Which of the two happens is an implementation
    detail of where the junk is caught; that it is never *calibrated* is the guarantee,
    and writing it this way means a later change to the field validator relaxes the
    mechanism without silently relaxing the promise.
    """
    try:
        prediction = Prediction[float].model_validate(
            _payload(junk), context=trusted_deserialization_context()
        )
    except ValidationError:
        return
    assert not prediction.calibrated, (
        f"in_distribution={junk!r} loaded as calibrated through the trusted context; "
        "the gate requires an in-distribution input and could not read this one"
    )


def test_the_trusted_context_does_calibrate_a_well_formed_payload() -> None:
    """The premise: this payload and context are otherwise accepted.

    Without it every assertion above could pass on a payload that was rejected for an
    unrelated reason, which is how a gate comes to be "tested" by inputs that never
    reach it.
    """
    prediction = Prediction[float].model_validate(
        _payload(True), context=trusted_deserialization_context()
    )
    assert prediction.calibrated
    assert prediction.in_distribution


def test_a_well_formed_out_of_distribution_payload_loses_calibration() -> None:
    """The documented arm, next to the junk arm, so the pair reads as one rule."""
    prediction = Prediction[float].model_validate(
        _payload(False), context=trusted_deserialization_context()
    )
    assert not prediction.calibrated
    assert not prediction.in_distribution


@pytest.mark.parametrize("junk", _JUNK)
def test_junk_is_not_calibrated_without_the_token_either(junk: Any) -> None:
    """No context at all: the other half of the `and` must still hold.

    A gate with two conditions needs the case where each fails alone — this log has
    recorded that for guards often enough that the omission is the predictable one.
    """
    try:
        prediction = Prediction[float].model_validate(_payload(junk))
    except ValidationError:
        return
    assert not prediction.calibrated
