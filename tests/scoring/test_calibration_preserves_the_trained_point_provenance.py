"""Conformal recalibration reset a trained point estimate to "not trained".

`Prediction.point_from_trained_model` exists for one reason, stated in its own
docstring: a trained point often ships with an *uncalibrated* heuristic interval, which
would otherwise be "byte-identical in the honesty flags to a fully heuristic
prediction". The flag is what makes *trained point, uncalibrated interval*
distinguishable from *heuristic point*, and both report surfaces read it —
`report/html.py` prints "(… point estimate — not from a trained model)" when it is
False, and `report/pdf.py` qualifies the printed number with it.

`ConformalCalibrator.calibrate` rebuilt its result through `Prediction.calibrated_by`
and forwarded `value`, `in_distribution` and `notes` from the incoming prediction — but
not `point_from_trained_model`, which therefore fell back to the parameter's default of
`False`. So recalibrating a genuine Rule Set 3 or PRIDICT2 point produced a prediction
that denied being trained, and a report built from it would carry the disclaimer written
for heuristic baselines.

The sibling path had it right. `Prediction.combine` propagates the flag through the same
constructor and says why in a comment — "a combined point rests on a trained model only
when *every* input point did". Two call sites, one parameter, one of them forgetting:
**when two places construct the same thing, check both; one being right is not
evidence.**

Why the suite did not notice: `calibrated_by`'s own tests pass the flag explicitly, and
the calibrator's tests assert coverage and interval width — the numbers it exists to
correct — never the provenance it carries along. A boolean default is the one parameter
no call site has to defend, and a suite that always passes it explicitly cannot measure
what omitting it does.

Found by flipping the default (`scripts/mutate.py --mode dflt`): the mutation
`calibrated_by(point_from_trained_model=False -> True)` survived the entire suite.
"""

from __future__ import annotations

from alleleforge.scoring.uncertainty import ConformalCalibrator
from alleleforge.types.prediction import Prediction, UncertaintyMethod


def _trained(value: float, half: float) -> Prediction[float]:
    """A trained point estimate with a heuristic interval — the shape at issue."""
    return Prediction[float](
        value=value,
        interval=(value - half, value + half),
        method=UncertaintyMethod.HEURISTIC,
        point_from_trained_model=True,
    )


def _fitted() -> ConformalCalibrator:
    calibration = [_trained(0.5, 0.1) for _ in range(20)]
    truths = [0.5 + 0.01 * i for i in range(20)]
    return ConformalCalibrator(level=0.8).fit(calibration, truths)


def test_recalibration_keeps_a_trained_point_marked_trained() -> None:
    """The flag must survive the calibrator, as it survives `combine`."""
    recalibrated = _fitted().calibrate(_trained(0.7, 0.1))
    assert recalibrated.calibrated, "premise: an in-distribution input is calibrated"
    assert recalibrated.point_from_trained_model, (
        "conformal recalibration reset a trained point estimate to "
        "point_from_trained_model=False; the report would then disclaim it as a "
        "heuristic baseline"
    )


def test_the_authorized_constructor_defaults_to_an_untrained_point() -> None:
    """Omitting the flag must mean "not trained", not "trained".

    Fixing the calibrator made both production call sites pass the flag explicitly,
    which would leave the *default* unreachable — and an unreachable default is one
    nobody can be wrong about until a third caller omits it. The default is the
    fail-safe: a caller who says nothing gets the claim that under-states the model,
    never the one that over-states it.
    """
    prediction = Prediction[float].calibrated_by(
        value=0.5,
        interval=(0.4, 0.6),
        method=UncertaintyMethod.CONFORMAL,
    )
    assert not prediction.point_from_trained_model


def test_recalibration_does_not_invent_a_trained_point() -> None:
    """The other direction: a heuristic point must not come back trained.

    The case where the propagation must *not* fire. Forwarding a field is only correct
    if it forwards the absence too, and a guard that only ever sees `True` cannot tell
    propagation from a hardcoded `True`.
    """
    heuristic = Prediction[float](
        value=0.7,
        interval=(0.6, 0.8),
        method=UncertaintyMethod.HEURISTIC,
        point_from_trained_model=False,
    )
    assert not _fitted().calibrate(heuristic).point_from_trained_model


def test_an_out_of_distribution_trained_point_keeps_its_provenance() -> None:
    """OOD refuses *calibration*, not provenance.

    An OOD input resolves to `calibrated=False` by the honesty contract. That is a
    statement about the interval, and it must not quietly also erase what the point
    estimate came from — the two flags answer different questions.
    """
    ood = Prediction[float](
        value=0.7,
        interval=(0.6, 0.8),
        method=UncertaintyMethod.HEURISTIC,
        in_distribution=False,
        point_from_trained_model=True,
    )
    recalibrated = _fitted().calibrate(ood)
    assert not recalibrated.calibrated, "premise: OOD cannot be calibrated"
    assert recalibrated.point_from_trained_model
