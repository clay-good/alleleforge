"""Tests for SpCas9 on-target efficiency scorers."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path

import pytest

from alleleforge.model_zoo.registry import (
    ChecksumError,
    ConsentError,
    ModelCard,
    ModelRegistry,
)
from alleleforge.scoring.backbone import StubEmbedder
from alleleforge.scoring.base import ensure_prediction
from alleleforge.scoring.cas9_efficiency import (
    EnsembleEfficiencyScorer,
    RuleSet3Scorer,
    TracrRNA,
    TrainedRuleSet3Scorer,
)
from alleleforge.scoring.uncertainty import OODDetector
from alleleforge.types.prediction import UncertaintyMethod

_CTX = "ACGTACGTACGTACGTACGTAGG"  # protospacer + PAM-ish context

# Golden Rule Set 3 raw activity z-scores for three 30-nt contexts under the
# Chen2013 tracr, captured from upstream rs3 v0.0.18 `predict_seq`. The trained
# scorer must reproduce these exactly (the parity contract). See
# scripts/export_rs3_booster.py for how the pinned booster is derived.
_RS3_GOLDEN_CONTEXTS = (
    "GACGGAGGCTAAGCGTCGCAAGGCGTCGTA",
    "AAAATTTTAAAATTTTAAAATTTTAAAATT",
    "GCGCGCGCGCGCGCGCGCGCGGGCGCGCAT",
)
_RS3_GOLDEN_CHEN2013 = (-0.349795, -2.422439, -1.315348)


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


def test_ensemble_on_stub_is_honest_heuristic() -> None:
    # The weight-free stub embedder is content-hashed noise, not a trained
    # backbone: the result must be an uncalibrated, heuristic-tagged prediction
    # so a heuristic is never mistaken for a trained model.
    p = EnsembleEfficiencyScorer(embedder=StubEmbedder(dim=16)).score(_CTX)
    assert p.method is UncertaintyMethod.HEURISTIC
    assert p.interval[0] <= p.value <= p.interval[1]
    assert p.interval_level == 0.80
    assert p.calibrated is False


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


# -- trained Rule Set 3 (consent-gated model zoo) -----------------------------
#
# The gate behaviour (license + consent + checksum) is exercised in CI without
# the cas9-rs3 extra or the real booster; the actual forward pass + bit-parity
# with upstream rs3 is the opt-in `real_weights` test at the bottom.

_FAKE_BOOSTER = b"pretend-lightgbm-text-booster"
_FAKE_SHA = hashlib.sha256(_FAKE_BOOSTER).hexdigest()


def _fake_rs3_card(sha: str = _FAKE_SHA) -> ModelCard:
    return ModelCard(
        name="rule-set-3",
        version="1.0",
        chemistry="cas9_nuclease",
        training_data="synthetic",
        intended_use="testing the trained RS3 consent/checksum gate",
        out_of_scope_use="anything real",
        license="Apache-2.0",
        citation="AlleleForge test suite",
        checkpoint_sha256=sha,
        source_url="https://example.invalid/RuleSet3.txt",
    )


def test_trained_rs3_model_card_is_apache() -> None:
    card = TrainedRuleSet3Scorer().model_card()
    assert card.name == "rule-set-3"
    assert card.license == "Apache-2.0"  # the rs3 package license (not BSD)


def test_trained_rs3_requires_consent(tmp_path: Path) -> None:
    # The bundled card pins a checkpoint hash, so resolution takes the download
    # path; without consent the gate refuses to fetch.
    scorer = TrainedRuleSet3Scorer(cache_dir=tmp_path, downloader=lambda u, d: None)
    with pytest.raises(ConsentError):
        scorer.resolve_weights()


def test_trained_rs3_gate_downloads_and_verifies(tmp_path: Path) -> None:
    registry = ModelRegistry({"rule-set-3": _fake_rs3_card()})
    fetched: list[str] = []

    def downloader(url: str, dest: Path) -> None:
        fetched.append(url)
        dest.write_bytes(_FAKE_BOOSTER)

    scorer = TrainedRuleSet3Scorer(
        registry=registry, consent=True, cache_dir=tmp_path, downloader=downloader
    )
    path = scorer.resolve_weights()
    assert path is not None and Path(path).read_bytes() == _FAKE_BOOSTER
    assert fetched == ["https://example.invalid/RuleSet3.txt"]
    checkpoint = scorer.model_checkpoint()
    assert checkpoint is not None and checkpoint.sha256 == _FAKE_SHA


def test_trained_rs3_rejects_corrupt_download(tmp_path: Path) -> None:
    registry = ModelRegistry({"rule-set-3": _fake_rs3_card()})
    scorer = TrainedRuleSet3Scorer(
        registry=registry,
        consent=True,
        cache_dir=tmp_path,
        downloader=lambda u, d: d.write_bytes(b"corrupted"),
    )
    with pytest.raises(ChecksumError):
        scorer.resolve_weights()


def test_trained_rs3_rejects_wrong_length() -> None:
    # The 30-nt contract is enforced before any model load (no extra needed).
    with pytest.raises(ValueError, match="30-nt"):
        TrainedRuleSet3Scorer().predict_raw(["ACGT"])


def test_trained_rs3_without_extra_raises() -> None:
    # When the cas9-rs3 extra is absent, scoring fails with a helpful message
    # rather than a bare ImportError. Skip where lightgbm is actually installed.
    if importlib.util.find_spec("lightgbm") is not None:
        pytest.skip("cas9-rs3 extra is installed; missing-extra path not exercised")
    with pytest.raises(RuntimeError, match="cas9-rs3"):
        TrainedRuleSet3Scorer().predict_raw(["A" * 30])


# -- opt-in: real trained model, bit-parity with upstream rs3 -----------------


@pytest.mark.real_weights
def test_trained_rs3_parity_with_upstream(tmp_path: Path) -> None:
    """The trained scorer reproduces upstream rs3 z-scores exactly.

    Opt-in: needs the cas9-rs3 extra (lightgbm, sglearn) and the version-stable
    booster at ``$ALLELEFORGE_RS3_BOOSTER``. Skipped otherwise, so CI stays
    weight-free.
    """
    if importlib.util.find_spec("lightgbm") is None or importlib.util.find_spec("sglearn") is None:
        pytest.skip("cas9-rs3 extra (lightgbm, sglearn) not installed")
    booster_path = os.environ.get("ALLELEFORGE_RS3_BOOSTER")
    if not booster_path or not Path(booster_path).exists():
        pytest.skip("set ALLELEFORGE_RS3_BOOSTER to the RuleSet3.txt text booster")

    booster_bytes = Path(booster_path).read_bytes()
    sha = hashlib.sha256(booster_bytes).hexdigest()
    registry = ModelRegistry({"rule-set-3": _fake_rs3_card(sha=sha)})
    scorer = TrainedRuleSet3Scorer(
        registry=registry,
        consent=True,
        cache_dir=tmp_path,
        downloader=lambda u, d: d.write_bytes(booster_bytes),
        tracr=TracrRNA.CHEN_2013,
    )

    raw = scorer.predict_raw(list(_RS3_GOLDEN_CONTEXTS))
    for got, want in zip(raw, _RS3_GOLDEN_CHEN2013, strict=True):
        assert abs(got - want) < 1e-4, f"RS3 parity drift: {got} vs {want}"

    # The Prediction wraps the trained point through a monotone logistic squash.
    pred = scorer.score(_RS3_GOLDEN_CONTEXTS[0])
    assert 0.0 <= pred.value <= 1.0
    assert pred.method is UncertaintyMethod.HEURISTIC  # the interval is heuristic
    assert pred.calibrated is False
    assert pred.interval[0] <= pred.value <= pred.interval[1]

    # The tracrRNA scaffold is a real RS3 feature: scores differ by scaffold.
    hsu = TrainedRuleSet3Scorer(
        registry=registry,
        consent=True,
        cache_dir=tmp_path,
        downloader=lambda u, d: d.write_bytes(booster_bytes),
        tracr=TracrRNA.HSU_2013,
    ).predict_raw([_RS3_GOLDEN_CONTEXTS[0]])
    assert hsu[0] != raw[0]
