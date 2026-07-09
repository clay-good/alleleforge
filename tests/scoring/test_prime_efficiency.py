"""Tests for prime-editing efficiency scoring and OOD honesty."""

from __future__ import annotations

import pytest

from alleleforge.scoring.prime_efficiency import DeepPrimeAdapter, GenETAdapter, PridictScorer
from alleleforge.types.guide import PegRNA, Spacer, ThreePrimeMotif
from alleleforge.types.prediction import UncertaintyMethod
from alleleforge.types.sequence import DNASequence

_SCAFFOLD = DNASequence("GTTTTAGAGCTAGAAATAGCAAG")


def _peg(
    *, pbs: str, rtt: str, homology: int = 5, motif: ThreePrimeMotif = ThreePrimeMotif.TEVOPREQ1
) -> PegRNA:
    return PegRNA(
        spacer=Spacer(sequence=DNASequence("ACGTACGTACGTACGTACGT")),
        scaffold=_SCAFFOLD,
        rtt=DNASequence(rtt),
        pbs=DNASequence(pbs),
        three_prime_motif=motif,
        rtt_homology_3prime=homology,
    )


def test_returns_calibrated_prediction() -> None:
    p = PridictScorer().score(_peg(pbs="ACGTACGTACGTA", rtt="ACGTACGTACGTACGT"))
    assert 0.0 <= p.value <= 1.0
    assert p.interval[0] <= p.value <= p.interval[1]
    assert p.interval_level == 0.80
    assert p.method is UncertaintyMethod.HEURISTIC


def test_ood_fires_outside_hek_k562() -> None:
    peg = _peg(pbs="ACGTACGTACGTA", rtt="ACGTACGTACGTACGT")
    assert PridictScorer().score(peg).in_distribution is True  # default context
    assert PridictScorer().score(peg, cell_context="HEK293T").in_distribution is True
    assert PridictScorer().score(peg, cell_context="primary_T_cell").in_distribution is False


def test_epegrna_motif_raises_efficiency() -> None:
    with_motif = PridictScorer().score(_peg(pbs="ACGTACGTACGTA", rtt="ACGTACGTACGTACGT"))
    without = PridictScorer().score(
        _peg(pbs="ACGTACGTACGTA", rtt="ACGTACGTACGTACGT", motif=ThreePrimeMotif.NONE)
    )
    assert with_motif.value > without.value


def test_pbs_length_optimum() -> None:
    optimal = PridictScorer().score(_peg(pbs="ACGTACGTACGTA", rtt="ACGTACGTACGTACGT"))  # 13 nt
    short = PridictScorer().score(_peg(pbs="ACGTACGT", rtt="ACGTACGTACGTACGT"))  # 8 nt
    assert optimal.value > short.value


def test_chromatin_adjustment() -> None:
    # an open-chromatin signal nudges efficiency up
    import tempfile
    from pathlib import Path

    from alleleforge.data.annotations import EncodeTracks
    from alleleforge.types.sequence import GenomicInterval, Strand

    bg = Path(tempfile.mkdtemp()) / "t.bedgraph"
    bg.write_text("DNase\tchr2\t0\t100\t5.0\n")
    tracks = EncodeTracks.from_bedgraph(bg)
    interval = GenomicInterval(chrom="chr2", start=10, end=30, strand=Strand.PLUS)
    peg = _peg(pbs="ACGTACGTACGTA", rtt="ACGTACGTACGTACGT")
    base = PridictScorer().score(peg).value
    adjusted = PridictScorer().score(peg, chromatin=(tracks, interval, "DNase")).value
    assert adjusted >= base


def test_model_card() -> None:
    # The transparent geometry baseline carries its own honest card, not the
    # trained pridict2 card (so default provenance never misreports a trained
    # model); the scorer's own name is honest too.
    scorer = PridictScorer()
    card = scorer.model_card()
    assert card.name == "pridict2-baseline"
    assert scorer.name == "pridict2-baseline"
    assert "not the trained PRIDICT2.0 model" in " ".join(card.known_failure_modes)


def test_adapters_interface() -> None:
    assert DeepPrimeAdapter().name == "DeepPrime"
    # Both trained adapters now ship a bundled, license-gated model card.
    assert DeepPrimeAdapter().model_card().name == "deepprime"
    assert GenETAdapter().model_card().name == "genet"


# --- R1: the trained adapters resolve weights through the consent gate -----------


def test_adapter_score_requires_consent() -> None:
    from alleleforge.model_zoo.registry import ConsentError

    peg = _peg(pbs="ACGTACGTACGTA", rtt="ACGTACGTACGTACGT")
    with pytest.raises(ConsentError, match="consent"):
        DeepPrimeAdapter().score(peg)


def test_adapter_blocks_commercial_use() -> None:
    from alleleforge.model_zoo.registry import LicenseError, ModelUse

    # The trained adapters are research-only; the license gate refuses commercial use.
    with pytest.raises(LicenseError, match="commercial"):
        GenETAdapter(use=ModelUse.COMMERCIAL, consent=True).resolve_weights()


def test_adapter_research_consent_records_checkpoint() -> None:
    # The bundled card pins no hash, so research consent passes the authorize gate
    # and the resolved checkpoint is recorded for provenance.
    adapter = DeepPrimeAdapter(consent=True)
    assert adapter.resolve_weights() is None  # load by source after the gate
    checkpoint = adapter.model_checkpoint()
    assert checkpoint is not None
    assert checkpoint.name == "deepprime" and checkpoint.chemistry == "prime"


def test_adapter_pinned_weights_download_and_verify(tmp_path: object) -> None:
    import hashlib
    from pathlib import Path

    from alleleforge.model_zoo.registry import ModelCard, ModelRegistry

    weights = b"trained-prime-weights"
    sha = hashlib.sha256(weights).hexdigest()
    card = ModelCard(
        name="deepprime",
        version="1.0",
        chemistry="prime",
        training_data="synthetic",
        intended_use="testing the consent flow",
        out_of_scope_use="anything real",
        license="MIT",
        citation="AlleleForge test suite",
        known_failure_modes=("documented test failure mode",),
        checkpoint_sha256=sha,
        source_url="https://example.invalid/deepprime.ckpt",
    )
    registry = ModelRegistry({"deepprime": card})
    adapter = DeepPrimeAdapter(
        registry=registry,
        consent=True,
        cache_dir=Path(str(tmp_path)),
        downloader=lambda url, dest: dest.write_bytes(weights),
    )
    path = adapter.resolve_weights()
    assert path is not None and Path(path).read_bytes() == weights
    checkpoint = adapter.model_checkpoint()
    assert checkpoint is not None and checkpoint.sha256 == sha and checkpoint.chemistry == "prime"
