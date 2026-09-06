"""Tests for ensembles, evidential/quantile heads, calibration, and OOD."""

from __future__ import annotations

import random

import pytest

from alleleforge.scoring.backbone import StubEmbedder
from alleleforge.scoring.uncertainty import (
    ConformalCalibrator,
    DeepEnsemble,
    EnsembleResult,
    EvidentialParams,
    IsotonicCalibrator,
    OODDetector,
    empirical_coverage,
    ensemble_prediction,
    evidential_prediction,
    expected_calibration_error,
    min_calibration_size,
    quantile_prediction,
    to_prediction,
)
from alleleforge.types.prediction import Prediction, UncertaintyMethod

# -- to_prediction ------------------------------------------------------------


def test_to_prediction_contains_point() -> None:
    p = to_prediction(0.9, (0.2, 0.5), method=UncertaintyMethod.ENSEMBLE)
    assert p.interval[0] <= p.value <= p.interval[1]  # interval widened to hold the point


def test_to_prediction_records_interval_repair() -> None:
    # A point outside its own interval signals an inconsistent head: the repair
    # is recorded as an auditable note rather than applied silently.
    p = to_prediction(0.9, (0.2, 0.5), method=UncertaintyMethod.ENSEMBLE)
    assert any("widened to contain point estimate" in n for n in p.notes)


def test_to_prediction_consistent_head_has_no_note() -> None:
    p = to_prediction(0.4, (0.2, 0.5), method=UncertaintyMethod.ENSEMBLE)
    assert p.notes == ()


def test_ood_widens_and_stays_uncalibrated() -> None:
    # An OOD input can never present a narrow interval, even if members agree.
    agree = EnsembleResult((0.50, 0.501, 0.499, 0.50, 0.50))
    in_dist = ensemble_prediction(agree, in_distribution=True)
    ood = ensemble_prediction(agree, in_distribution=False)
    assert ood.interval_width > in_dist.interval_width
    assert ood.calibrated is False


def test_ood_floor_defeats_zero_width_agreement() -> None:
    # The failure the multiplicative factor alone missed: when ensemble members
    # agree *exactly* the half-width is 0, and 0 * factor == 0 — an OOD input could
    # still present a zero-width, maximally-confident interval. The additive floor
    # guarantees a strictly-positive width, wider than the (zero-width) in-dist one.
    exact = EnsembleResult((0.50, 0.50, 0.50, 0.50, 0.50))
    in_dist = ensemble_prediction(exact, in_distribution=True)
    ood = ensemble_prediction(exact, in_distribution=False)
    assert in_dist.interval_width == 0.0  # exact agreement -> degenerate in-dist interval
    assert ood.interval_width > 0.0  # ...but the OOD interval is never zero-width
    assert ood.calibrated is False


# -- DeepEnsemble -------------------------------------------------------------


def test_ensemble_basics() -> None:
    ens = DeepEnsemble(
        [lambda _x: 0.5, lambda _x: 0.6, lambda _x: 0.55, lambda _x: 0.52, lambda _x: 0.58]
    )
    assert ens.n_members == 5
    result = ens.predict("seq")
    p = ensemble_prediction(result)
    assert p.method is UncertaintyMethod.ENSEMBLE
    assert p.interval[0] <= p.value <= p.interval[1]
    assert p.interval_level == 0.80


def test_ensemble_interval_widens_on_disagreement() -> None:
    agree = ensemble_prediction(EnsembleResult((0.50, 0.51, 0.49, 0.50, 0.50)))
    disagree = ensemble_prediction(EnsembleResult((0.20, 0.80, 0.50, 0.10, 0.90)))
    assert disagree.interval_width > agree.interval_width  # OOD-style disagreement widens


def test_empty_ensemble_rejected() -> None:
    with pytest.raises(ValueError, match="at least one member"):
        DeepEnsemble([])


# -- evidential ---------------------------------------------------------------


def test_evidential_variance_split_and_interval() -> None:
    params = EvidentialParams(gamma=0.7, nu=2.0, alpha=3.0, beta=1.0)
    assert params.aleatoric_variance == pytest.approx(0.5)
    assert params.epistemic_variance == pytest.approx(0.25)
    p = evidential_prediction(params)
    assert p.method is UncertaintyMethod.EVIDENTIAL
    assert p.interval[0] <= 0.7 <= p.interval[1]


def test_evidential_param_validation() -> None:
    with pytest.raises(ValueError, match="alpha>1"):
        EvidentialParams(gamma=0.5, nu=1.0, alpha=1.0, beta=1.0)


# -- quantile -----------------------------------------------------------------


def test_quantile_prediction_reads_interval() -> None:
    q = {0.1: 0.4, 0.5: 0.6, 0.9: 0.85}
    p = quantile_prediction(q)
    assert p.method is UncertaintyMethod.QUANTILE
    assert p.value == pytest.approx(0.6)  # median default
    assert p.interval[0] == pytest.approx(0.4) and p.interval[1] == pytest.approx(0.85)


# -- isotonic calibration + ECE -----------------------------------------------


def _miscalibrated() -> tuple[list[float], list[float]]:
    # Underconfident: at confidence lv the true positive rate is sqrt(lv) > lv.
    confs: list[float] = []
    outs: list[float] = []
    for lv in (0.1, 0.3, 0.5, 0.7, 0.9):
        n, k = 20, round((lv**0.5) * 20)
        for j in range(n):
            confs.append(lv)
            outs.append(1.0 if j < k else 0.0)
    return confs, outs


def test_calibration_reduces_ece() -> None:
    confs, outs = _miscalibrated()
    ece_raw = expected_calibration_error(confs, outs, n_bins=10)
    cal = IsotonicCalibrator().fit(confs, outs)
    ece_cal = expected_calibration_error(cal.predict(confs), outs, n_bins=10)
    assert ece_raw > 0.1
    assert ece_cal < ece_raw


def test_isotonic_is_monotonic() -> None:
    cal = IsotonicCalibrator().fit([0.1, 0.2, 0.3, 0.4], [0.0, 1.0, 0.0, 1.0])
    out = cal.predict([0.1, 0.2, 0.3, 0.4])
    assert all(b >= a for a, b in zip(out, out[1:], strict=False))  # non-decreasing


def test_ece_perfect_calibration_is_low() -> None:
    confs = [0.0, 1.0] * 50  # confidence matches the empirical outcome exactly
    outs = [0.0, 1.0] * 50
    assert expected_calibration_error(confs, outs, n_bins=10) < 1e-9


def test_ece_input_guard() -> None:
    with pytest.raises(ValueError, match="equal-length"):
        expected_calibration_error([0.1], [0.0, 1.0])


# -- OOD detector -------------------------------------------------------------


def test_ood_flags_far_inputs() -> None:
    emb = StubEmbedder(dim=8)
    reference = emb.embed(["ACGTACGTAC", "ACGTACGTAG", "ACGTACGTAT", "ACGTACGTCC"])
    detector = OODDetector(reference, threshold=0.3)
    assert detector.is_in_distribution(reference[0])  # a training point is in-dist
    far = tuple(5.0 for _ in range(8))  # far from any unit-cube reference vector
    assert not detector.is_in_distribution(far)
    assert detector.distance(far) > detector.threshold


def test_ood_derives_threshold_from_reference() -> None:
    emb = StubEmbedder(dim=6)
    reference = emb.embed([f"SEQ{i:03d}" for i in range(8)])
    detector = OODDetector(reference, quantile=0.9)
    assert detector.threshold >= 0.0


def test_ood_empty_reference_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty reference"):
        OODDetector([])


# -- conformal interval recalibration -----------------------------------------


def _interval(center: float, half: float) -> object:
    return to_prediction(center, (center - half, center + half), method=UncertaintyMethod.ENSEMBLE)


def _miscalibrated_intervals(
    rng: random.Random, n: int, *, half: float, sigma: float
) -> tuple[list, list]:
    """Predictions whose intervals are far too narrow for the true spread."""
    preds, truths = [], []
    for _ in range(n):
        center = rng.uniform(0.0, 1.0)
        truths.append(center + rng.gauss(0.0, sigma))
        preds.append(_interval(center, half))
    return preds, truths


def test_empirical_coverage_counts_hits() -> None:
    preds = [_interval(0.5, 0.1), _interval(0.5, 0.1)]
    assert empirical_coverage(preds, [0.55, 0.9]) == 0.5  # one inside, one outside


def test_empirical_coverage_input_guard() -> None:
    with pytest.raises(ValueError, match="equal-length"):
        empirical_coverage([_interval(0.5, 0.1)], [0.5, 0.6])


@pytest.mark.parametrize("level", [0.8, 0.9])
def test_conformal_restores_coverage_to_nominal(level: float) -> None:
    # A badly under-covering set (intervals far too narrow) is recalibrated to
    # meet the target level — the finite-sample split-conformal guarantee.
    rng = random.Random(7)
    cal_p, cal_y = _miscalibrated_intervals(rng, 600, half=0.05, sigma=0.2)
    test_p, test_y = _miscalibrated_intervals(rng, 2000, half=0.05, sigma=0.2)
    assert empirical_coverage(test_p, test_y) < 0.4  # raw is badly miscalibrated

    cal = ConformalCalibrator(level=level).fit(cal_p, cal_y)
    recalibrated = [cal.calibrate(p) for p in test_p]
    coverage = empirical_coverage(recalibrated, test_y)
    assert coverage >= level - 0.03  # meets nominal (small finite-sample slack)


def test_conformal_preserves_relative_interval_width() -> None:
    rng = random.Random(11)
    cal_p, cal_y = _miscalibrated_intervals(rng, 400, half=0.05, sigma=0.2)
    cal = ConformalCalibrator(level=0.8).fit(cal_p, cal_y)
    narrow = cal.calibrate(_interval(0.5, 0.05))
    wide = cal.calibrate(_interval(0.5, 0.10))
    w_narrow = narrow.interval[1] - narrow.interval[0]
    w_wide = wide.interval[1] - wide.interval[0]
    assert w_wide == pytest.approx(2 * w_narrow)  # multiplicative scale preserves shape


def test_conformal_tags_method_and_calibrated_flag() -> None:
    rng = random.Random(3)
    cal_p, cal_y = _miscalibrated_intervals(rng, 200, half=0.05, sigma=0.2)
    cal = ConformalCalibrator(level=0.8).fit(cal_p, cal_y)
    out = cal.calibrate(_interval(0.5, 0.05))
    assert out.method is UncertaintyMethod.CONFORMAL
    assert out.calibrated is True and out.interval_level == 0.8


def test_conformal_does_not_narrow_ood_below_floor() -> None:
    # OOD widens, never narrows: recalibrating an out-of-distribution prediction
    # (calibrated stays False) must not shrink its interval below the additive
    # OOD floor. A conformal scale < 1 (an over-covering scorer) otherwise silently
    # narrows the OOD band into a narrow, confident-looking interval.
    from alleleforge.scoring.uncertainty import OOD_MIN_HALF_WIDTH

    # Deterministic calibration set -> scale == 0.5 (half-width 1.0, residual 0.5).
    cal_p = [_interval(0.5, 1.0) for _ in range(20)]
    cal = ConformalCalibrator(level=0.8).fit(cal_p, [1.0 for _ in range(20)])
    assert cal.scale == pytest.approx(0.5)

    ood = to_prediction(0.5, (0.49, 0.51), method=UncertaintyMethod.ENSEMBLE, in_distribution=False)
    assert ood.interval_width / 2 >= OOD_MIN_HALF_WIDTH  # input respects the floor
    out = cal.calibrate(ood)
    assert out.in_distribution is False and out.calibrated is False
    assert out.interval_width / 2 >= OOD_MIN_HALF_WIDTH  # ...output must too


def test_conformal_unfitted_raises() -> None:
    with pytest.raises(ValueError, match="not fitted"):
        ConformalCalibrator().calibrate(_interval(0.5, 0.1))


def test_conformal_rejects_degenerate_calibration_interval() -> None:
    with pytest.raises(ValueError, match="positive-width"):
        ConformalCalibrator().fit([_interval(0.5, 0.0)], [0.5])


def test_conformal_level_and_input_guards() -> None:
    with pytest.raises(ValueError, match="level must be"):
        ConformalCalibrator(level=1.5)
    with pytest.raises(ValueError, match="equal-length"):
        ConformalCalibrator().fit([_interval(0.5, 0.1)], [0.5, 0.6])


def test_a_too_small_calibration_set_does_not_claim_the_requested_coverage() -> None:
    """Three calibration points produced an interval labelled `@ 95%`.

    Split conformal takes the `ceil((n+1)*level)`-th smallest normalized residual, and
    when that rank exceeds `n` it falls back to the largest residual — correctly, it is
    the most conservative finite scale. But the guarantee that fallback carries is
    `n / (n + 1)`, not the level that was asked for. The code's comment said so; the
    *prediction* said `interval_level=0.95, calibrated=True` with no notes, which is
    unearned reassurance wearing the label of a measurement — in the module that
    implements this project's headline claim.
    """
    preds = [
        Prediction[float](value=v, interval=(v - 0.1, v + 0.1), method=UncertaintyMethod.HEURISTIC)
        for v in (0.2, 0.5, 0.8)
    ]
    calibrator = ConformalCalibrator(level=0.95).fit(preds, [0.25, 0.55, 0.85])

    assert calibrator.achieved_level == pytest.approx(3 / 4)
    out = calibrator.calibrate(preds[0])
    assert out.interval_level == pytest.approx(0.75), "the label must be the earned level"
    assert any("too small" in note for note in out.notes), out.notes
    assert str(min_calibration_size(0.95)) in " ".join(out.notes)


def test_a_large_enough_calibration_set_claims_the_full_level() -> None:
    """The correction must not make an honest calibration understate itself."""
    n = min_calibration_size(0.95)
    preds = [
        Prediction[float](
            value=0.05 * i,
            interval=(0.05 * i - 0.1, 0.05 * i + 0.1),
            method=UncertaintyMethod.HEURISTIC,
        )
        for i in range(n)
    ]
    calibrator = ConformalCalibrator(level=0.95).fit(preds, [0.05 * i + 0.02 for i in range(n)])

    assert calibrator.achieved_level == pytest.approx(0.95)
    out = calibrator.calibrate(preds[0])
    assert out.interval_level == pytest.approx(0.95)
    assert not any("too small" in note for note in out.notes)


@pytest.mark.parametrize("level", [0.5, 0.8, 0.9, 0.95, 0.99])
def test_the_minimum_calibration_size_is_exact(level: float) -> None:
    """The closed form `ceil(level / (1 - level))` is wrong in binary floating point.

    At the project's own default of 0.80 it evaluates to 4.000000000000001 and rounds
    to 5, overstating the requirement by one.
    """
    import math

    n = min_calibration_size(level)
    assert math.ceil((n + 1) * level) <= n, "the returned size does not support the level"
    assert n == 1 or math.ceil(n * level) > n - 1, "a smaller size would also have worked"
