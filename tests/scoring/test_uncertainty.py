"""Tests for ensembles, evidential/quantile heads, calibration, and OOD."""

from __future__ import annotations

import pytest

from alleleforge.scoring.backbone import StubEmbedder
from alleleforge.scoring.uncertainty import (
    DeepEnsemble,
    EnsembleResult,
    EvidentialParams,
    IsotonicCalibrator,
    OODDetector,
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
