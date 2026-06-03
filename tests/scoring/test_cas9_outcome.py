"""Tests for SpCas9 nuclease outcome (indel spectrum) prediction."""

from __future__ import annotations

import math

import pytest

from alleleforge.model_zoo.registry import CardError
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


def test_unbundled_adapter_card_missing() -> None:
    with pytest.raises(CardError, match="no model card"):
        LindelAdapter().model_card()  # no 'lindel' card is bundled
