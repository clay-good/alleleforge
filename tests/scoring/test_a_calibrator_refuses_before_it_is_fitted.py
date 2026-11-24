"""Five refusals in the uncertainty layer that nothing exercised.

`scoring/uncertainty.py` is the honesty layer: it is what turns a point estimate into a
band somebody is allowed to quote. Its validators were uncovered — the same five lines
coverage lists as unexecuted — and deleting each one survived the suite.

They are not defensive-impossible branches. Every one is reachable through the public
API, and `IsotonicCalibrator` and `ConformalCalibrator` are both exported in
`alleleforge.scoring.__all__`, so "a caller would never do that" is not available as an
excuse: an unfitted calibrator is exactly what a caller holds before calling `fit`.

The one that matters most is the pair of *unfitted* guards. Without them, a calibrator
that has learned nothing would answer anyway — from a `None` scale or an empty
interpolation table — and the number it returned would be presented as calibrated.
A refusal is the only honest answer there, and this file is what keeps it.

Found by deleting each refusal (`scripts/mutate.py --mode raise`); all five survived
their package list.
"""

from __future__ import annotations

import pytest

from alleleforge.scoring.uncertainty import (
    DEFAULT_INTERVAL_LEVEL,
    ConformalCalibrator,
    IsotonicCalibrator,
    check_interval_level_is_honorable,
    min_calibration_size,
)

# -- IsotonicCalibrator -------------------------------------------------------


def test_an_unfitted_isotonic_calibrator_refuses_to_answer() -> None:
    """The honest answer before `fit` is a refusal, not an interpolation of nothing."""
    with pytest.raises(ValueError, match="not fitted"):
        IsotonicCalibrator().predict_one(0.5)


def test_a_fitted_isotonic_calibrator_does_answer() -> None:
    """The premise, and the case the guard must not fire on."""
    calibrator = IsotonicCalibrator().fit([0.0, 0.5, 1.0], [0.1, 0.4, 0.9])
    assert calibrator.predict_one(0.5) == pytest.approx(0.4, abs=0.2)


@pytest.mark.parametrize(
    "x, y",
    [
        ([], []),
        ([0.1], []),
        ([], [0.1]),
        ([0.1, 0.2], [0.3]),
    ],
    ids=["both-empty", "empty-y", "empty-x", "mismatched-lengths"],
)
def test_isotonic_fit_refuses_empty_or_ragged_input(x: list[float], y: list[float]) -> None:
    """Both halves of the condition, each failing on its own.

    A guard reading `len(x) != len(y) or not x` needs the ragged case *and* the empty
    case; a fixture that trips both measures neither.
    """
    with pytest.raises(ValueError, match="non-empty, equal-length"):
        IsotonicCalibrator().fit(x, y)


# -- ConformalCalibrator ------------------------------------------------------


def test_an_unfitted_conformal_calibrator_has_no_scale() -> None:
    """`scale` and `achieved_level` are the two reads that must refuse."""
    calibrator = ConformalCalibrator(level=0.8)
    with pytest.raises(ValueError, match="not fitted"):
        _ = calibrator.scale
    with pytest.raises(ValueError, match="not fitted"):
        _ = calibrator.achieved_level


@pytest.mark.parametrize("level", [0.0, 1.0, -0.1, 1.5, 2.0])
def test_a_conformal_level_outside_the_open_unit_interval_is_refused(
    level: float,
) -> None:
    """Both ends are closed out, not just the obviously silly values.

    `0.0` and `1.0` are the interesting cases: a coverage level of exactly 1 reads as
    "always covered", which no finite calibration set can guarantee, and exactly 0 is a
    band with no content. Neither is a typo a reader would notice in a config file.
    """
    with pytest.raises(ValueError, match="level must be in"):
        ConformalCalibrator(level=level)


def test_a_conformal_level_inside_the_interval_is_accepted() -> None:
    for level in (0.5, 0.8, 0.95, 0.99):
        assert ConformalCalibrator(level=level).level == level


# -- the design-path interval level -------------------------------------------


def test_the_default_interval_level_is_the_only_one_a_design_run_honors() -> None:
    """Asking for a level nothing recomputes must fail loudly, not relabel the band.

    The refusal exists because a 95% request once produced 80%-wide bands under a 95%
    provenance line — a narrower guarantee than the number claimed. Deleting it returns
    to exactly that.
    """
    check_interval_level_is_honorable(DEFAULT_INTERVAL_LEVEL)  # does not raise

    with pytest.raises(ValueError, match="cannot be honored") as refused:
        check_interval_level_is_honorable(0.95)
    message = str(refused.value)
    # A remedy the caller can act on, in their own vocabulary: they set this in a file
    # or an environment variable, and a remedy they must translate is half a remedy.
    assert "config.toml" in message
    assert "ALLELEFORGE_INTERVAL_LEVEL" in message


# -- min_calibration_size, which carries the same guard a second time ---------


def test_min_calibration_size_refuses_a_level_outside_the_unit_interval() -> None:
    """The same sentence is raised in two places, and only one of them was reached.

    `ConformalCalibrator.__init__` and `min_calibration_size` both guard `0 < level < 1`
    with a byte-identical message. Deleting the one in `min_calibration_size` left the
    other standing, so every test that asked a calibrator for a bad level still passed
    and the deletion was invisible — the duplicated message is exactly what hides it.

    When two places raise the same sentence, a test that exercises one proves nothing
    about the other.
    """
    for level in (0.0, 1.0, -0.5, 1.5):
        with pytest.raises(ValueError, match="level must be in"):
            min_calibration_size(level)


def test_min_calibration_size_matches_the_documented_counts() -> None:
    """The premise, and the values the docstring commits to.

    Pinned because the function deliberately searches the real condition instead of the
    closed form `ceil(level / (1 - level))`, which evaluates to 4.000000000000001 for
    0.80 in binary floating point and would overstate the requirement by one on this
    project's own default level.
    """
    assert min_calibration_size(0.95) == 19
    assert min_calibration_size(0.80) == 4
