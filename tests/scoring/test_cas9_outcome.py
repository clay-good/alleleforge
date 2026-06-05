"""Tests for SpCas9 nuclease outcome (indel spectrum) prediction."""

from __future__ import annotations

import math

import pytest

from alleleforge.scoring.cas9_outcome import (
    InDelphiAdapter,
    LindelAdapter,
    MicrohomologyOutcomePredictor,
    ensemble_outcome,
)

_CTX = "AACGTCAACGTCAACGTCAAGGTTGGTTGGTTACGT"  # repeats -> microhomologies
_CUT = 18


def test_distribution_is_normalized() -> None:
    outcome = MicrohomologyOutcomePredictor().predict(_CTX, _CUT)
    assert math.isclose(sum(a.probability for a in outcome.alleles), 1.0, abs_tol=1e-6)


def test_contains_mmej_deletions_and_insertions() -> None:
    outcome = MicrohomologyOutcomePredictor().predict(_CTX, _CUT)
    alleles = [a.allele for a in outcome.alleles]
    assert any(a.startswith("del") for a in alleles)  # microhomology deletions
    assert any(a.startswith("ins1") for a in alleles)  # templated 1-bp insertions


def test_is_deterministic() -> None:
    a = MicrohomologyOutcomePredictor().predict(_CTX, _CUT)
    b = MicrohomologyOutcomePredictor().predict(_CTX, _CUT)
    assert [(x.allele, x.probability) for x in a.alleles] == [
        (x.allele, x.probability) for x in b.alleles
    ]


def test_frameshift_marking_for_knockout() -> None:
    outcome = MicrohomologyOutcomePredictor().predict(_CTX, _CUT, mark_frameshift=True)
    # 1-bp insertions and out-of-frame deletions are intended for a knock-out
    assert outcome.p_intended > 0.0
    for a in outcome.alleles:
        if a.allele.startswith("ins1"):
            assert a.is_intended
    no_mark = MicrohomologyOutcomePredictor().predict(_CTX, _CUT, mark_frameshift=False)
    assert no_mark.p_intended == 0.0


def test_cut_out_of_range_raises() -> None:
    with pytest.raises(ValueError, match="outside context"):
        MicrohomologyOutcomePredictor().predict("ACGT", 99)


def test_model_card() -> None:
    assert MicrohomologyOutcomePredictor().model_card().name == "indelphi"


# -- ensemble agreement -------------------------------------------------------


def test_ensemble_identical_predictors_full_agreement() -> None:
    o = MicrohomologyOutcomePredictor().predict(_CTX, _CUT)
    merged, agreement = ensemble_outcome([o, o, o])
    assert agreement == 1.0
    assert math.isclose(sum(a.probability for a in merged.alleles), 1.0, abs_tol=1e-6)


def test_ensemble_disagreement_lowers_agreement() -> None:
    a = MicrohomologyOutcomePredictor().predict(_CTX, _CUT)
    b = MicrohomologyOutcomePredictor().predict(_CTX, _CUT + 6)  # a different cut
    _merged, agreement = ensemble_outcome([a, b])
    assert 0.0 <= agreement <= 1.0


def test_ensemble_empty_raises() -> None:
    with pytest.raises(ValueError, match="at least one"):
        ensemble_outcome([])


# -- trained adapters (interface only; weights gated) -------------------------


def test_indelphi_adapter_interface() -> None:
    adapter = InDelphiAdapter()
    assert adapter.name == "inDelphi"
    assert adapter.model_card().name == "indelphi"


def test_lindel_adapter_card_now_bundled() -> None:
    # Lindel ships a bundled, license-gated card (research-only).
    assert LindelAdapter().model_card().name == "lindel"


def test_outcome_adapter_predict_requires_consent() -> None:
    from alleleforge.model_zoo.registry import ConsentError

    with pytest.raises(ConsentError, match="consent"):
        InDelphiAdapter().predict("ACGTACGTACGTACGTACGTACGT", 17)


def test_outcome_adapter_pinned_weights_download_and_verify(tmp_path: object) -> None:
    import hashlib
    from pathlib import Path

    from alleleforge.model_zoo.registry import ModelCard, ModelRegistry

    weights = b"trained-indelphi-weights"
    sha = hashlib.sha256(weights).hexdigest()
    card = ModelCard(
        name="indelphi",
        version="1.0",
        chemistry="cas9_nuclease",
        training_data="synthetic",
        intended_use="testing the consent flow",
        out_of_scope_use="anything real",
        license="MIT",
        citation="AlleleForge test suite",
        checkpoint_sha256=sha,
        source_url="https://example.invalid/indelphi.ckpt",
    )
    adapter = InDelphiAdapter(
        registry=ModelRegistry({"indelphi": card}),
        consent=True,
        cache_dir=Path(str(tmp_path)),
        downloader=lambda url, dest: dest.write_bytes(weights),
    )
    path = adapter.resolve_weights()
    assert path is not None and Path(path).read_bytes() == weights
    checkpoint = adapter.model_checkpoint()
    assert checkpoint is not None and checkpoint.sha256 == sha
