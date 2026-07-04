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
    quantile_prediction,
    to_prediction,
)
from alleleforge.types.prediction import UncertaintyMethod

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
