"""Tests for SpCas9 nuclease outcome (indel spectrum) prediction."""

from __future__ import annotations

import math

import pytest

from alleleforge.scoring.cas9_outcome import (
    InDelphiAdapter,
    LindelAdapter,
    MicrohomologyOutcomePredictor,
    _lindel_outcome,
    _lindel_window,
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
    # The transparent MMEJ baseline carries its own honest card, not the trained
    # inDelphi card (so default provenance never misreports a trained model).
    card = MicrohomologyOutcomePredictor().model_card()
    assert card.name == "indelphi-mh-baseline"
    assert "not the trained inDelphi model" in " ".join(card.known_failure_modes)


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


def test_ensemble_merged_order_is_deterministic_on_ties() -> None:
    # Two equal-probability alleles must merge into a deterministic order
    # (probability desc, then allele name asc) independent of the input allele
    # order — the merge iterated a set previously, so the tie order and the
    # float summation of `total` followed hash-seed order and varied run-to-run.
    from alleleforge.types.edit import AlleleOutcome, EditOutcome

    forward = EditOutcome(
        alleles=(
            AlleleOutcome(allele="A", probability=0.5),
            AlleleOutcome(allele="B", probability=0.5),
        ),
        partial=False,
    )
    reversed_ = EditOutcome(
        alleles=(
            AlleleOutcome(allele="B", probability=0.5),
            AlleleOutcome(allele="A", probability=0.5),
        ),
        partial=False,
    )
    m1, _ = ensemble_outcome([forward])
    m2, _ = ensemble_outcome([reversed_])
    assert [a.allele for a in m1.alleles] == ["A", "B"]
    assert [a.allele for a in m2.alleles] == ["A", "B"]  # input order does not matter
    assert m1.most_likely.allele == "A" == m2.most_likely.allele


# -- trained adapters (interface only; weights gated) -------------------------


def test_indelphi_adapter_interface() -> None:
    adapter = InDelphiAdapter()
    assert adapter.name == "inDelphi"
    assert adapter.model_card().name == "indelphi"


def test_lindel_adapter_card_now_bundled() -> None:
    # Lindel ships a bundled, license-gated card (research-only).
    assert LindelAdapter().model_card().name == "lindel"


# -- trained Lindel adapter ---------------------------------------------------


def test_lindel_window_extracts_60bp() -> None:
    ctx = "".join("ACGT"[i % 4] for i in range(80))
    win = _lindel_window(ctx, 40)
    assert len(win) == 60 and win == ctx[10:70].upper()


def test_lindel_window_too_short_raises() -> None:
    with pytest.raises(ValueError, match="flanking"):
        _lindel_window("ACGT" * 10, 20)  # only 40 bp, need >=30 each side of cut


def test_lindel_outcome_preserves_frameshift_mass() -> None:
    # The trained distribution maps to a normalized EditOutcome whose intended
    # (frameshift) mass equals Lindel's frameshift ratio exactly, even after the
    # tail is bucketed.
    probs = [0.5, 0.3, 0.1, 0.1]
    labels = ["-2+4", "0+1", "3", "1+C"]
    frameshift = [1.0, 1.0, 0.0, 1.0]  # only "3" is in-frame
    out = _lindel_outcome(probs, labels, frameshift, mark_frameshift=True, top_k=2)
    assert math.isclose(sum(a.probability for a in out.alleles), 1.0, abs_tol=1e-9)
    assert math.isclose(out.p_intended, 0.9, abs_tol=1e-9)  # 0.5 + 0.3 + 0.1 frameshift
    assert any(a.allele == "other_frameshift" for a in out.alleles)
    assert any(a.allele == "other_inframe" for a in out.alleles)


def test_lindel_outcome_no_frameshift_marking() -> None:
    out = _lindel_outcome([0.6, 0.4], ["-2+4", "3"], [1.0, 0.0], mark_frameshift=False, top_k=8)
    assert out.p_intended == 0.0  # nothing intended without knock-out marking


def test_lindel_predict_requires_consent() -> None:
    from alleleforge.model_zoo.registry import ConsentError

    with pytest.raises(ConsentError, match="consent"):
        LindelAdapter().predict("A" * 60, 30)


@pytest.mark.real_weights
def test_lindel_golden() -> None:
    """The adapter reproduces Lindel's frameshift ratio + top class on the example.

    Opt-in: set $ALLELEFORGE_LINDEL_REPO to a Lindel checkout (NumPy env). Skipped
    otherwise, so CI stays weight-free.
    """
    import importlib.util
    import os
    from pathlib import Path

    repo = os.environ.get("ALLELEFORGE_LINDEL_REPO")
    if not repo or not (Path(repo) / "Lindel" / "Model_weights.pkl").exists():
        pytest.skip("set ALLELEFORGE_LINDEL_REPO to a Lindel checkout")
    if importlib.util.find_spec("numpy") is None:
        pytest.skip("numpy not installed")

    seq60 = "TAACGTTATCAACGCCTATATTAAAGCGACCGTCGGTTGAACTGCGTGGATCAATGCGTC"  # PAM CGG @33
    out = LindelAdapter(repo_dir=repo, consent=True).predict(seq60, 30, mark_frameshift=True)
    assert math.isclose(sum(a.probability for a in out.alleles), 1.0, abs_tol=1e-3)
    assert abs(out.p_intended - 0.8912) < 0.02  # Lindel's golden frameshift ratio
    top = max(out.alleles, key=lambda a: a.probability)
    assert top.allele == "-2+4" and abs(top.probability - 0.3090) < 5e-3


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
        known_failure_modes=("documented test failure mode",),
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
