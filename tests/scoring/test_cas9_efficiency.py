"""Tests for SpCas9 on-target efficiency scorers."""

from __future__ import annotations

from alleleforge.scoring.backbone import StubEmbedder
from alleleforge.scoring.base import ensure_prediction
from alleleforge.scoring.cas9_efficiency import (
    EnsembleEfficiencyScorer,
    RuleSet3Scorer,
    TracrRNA,
)
from alleleforge.scoring.uncertainty import OODDetector
from alleleforge.types.prediction import UncertaintyMethod

_CTX = "ACGTACGTACGTACGTACGTAGG"  # protospacer + PAM-ish context


# -- Rule Set 3 baseline ------------------------------------------------------


def test_rs3_returns_calibrated_prediction() -> None:
    p = RuleSet3Scorer().score(_CTX)
    assert isinstance(ensure_prediction(p), type(p))
    assert 0.0 <= p.value <= 1.0
    assert p.interval[0] <= p.value <= p.interval[1]
    assert p.interval_level == 0.80
    assert p.method is UncertaintyMethod.HEURISTIC


def test_rs3_is_deterministic() -> None:
    assert RuleSet3Scorer().score(_CTX).value == RuleSet3Scorer().score(_CTX).value


def test_rs3_polyT_lowers_score() -> None:
    with_polyt = RuleSet3Scorer().score("ACGTACGTACGTTTTTACGT")
    without = RuleSet3Scorer().score("ACGTACGTACGTACGTACGT")
    assert without.value > with_polyt.value  # Pol III terminator penalized


def test_rs3_gc_optimum() -> None:
    optimal = RuleSet3Scorer().score("ACGTACGTACGTACGTACGT")  # GC ~ 0.5
    gc_poor = RuleSet3Scorer().score("AAAAAAAAAAAAAAAAAAAA")  # GC 0
    assert optimal.value > gc_poor.value


def test_rs3_tracrrna_feature() -> None:
    chen = RuleSet3Scorer(tracr=TracrRNA.CHEN_2013).score(_CTX)
    hsu = RuleSet3Scorer(tracr=TracrRNA.HSU_2013).score(_CTX)
    assert chen.value > hsu.value  # the optimized scaffold lifts predicted activity


def test_rs3_flags_n_as_ood() -> None:
    assert RuleSet3Scorer().score("ACGTACGTNCGTACGTACGT").in_distribution is False


def test_rs3_model_card() -> None:
    assert RuleSet3Scorer().model_card().name == "rule-set-3"


# -- backbone deep ensemble ---------------------------------------------------


def test_ensemble_returns_ensemble_prediction() -> None:
    p = EnsembleEfficiencyScorer(embedder=StubEmbedder(dim=16)).score(_CTX)
    assert p.method is UncertaintyMethod.ENSEMBLE
    assert p.interval[0] <= p.value <= p.interval[1]
    assert p.interval_level == 0.80
    assert p.calibrated is True


def test_ensemble_model_card() -> None:
    assert EnsembleEfficiencyScorer().model_card().name == "cas9-efficiency-ensemble"


def test_ensemble_ood_flag_plumbing() -> None:
    # With the stub embedder, OOD separation is exact-match; the real biological
    # human/non-human separation comes from the real backbone (real_weights).
    emb = StubEmbedder(dim=16)
    detector = OODDetector(emb.embed([_CTX]), threshold=0.0)
    scorer = EnsembleEfficiencyScorer(embedder=emb, ood=detector)
    assert scorer.score(_CTX).in_distribution is True
    assert scorer.score("TTTTTTTTTTTTTTTTTTTT").in_distribution is False


def test_ensemble_is_deterministic() -> None:
    a = EnsembleEfficiencyScorer(embedder=StubEmbedder(dim=16)).score(_CTX)
    b = EnsembleEfficiencyScorer(embedder=StubEmbedder(dim=16)).score(_CTX)
    assert a.value == b.value and a.interval == b.interval
