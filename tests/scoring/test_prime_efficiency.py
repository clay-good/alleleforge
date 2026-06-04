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
    assert PridictScorer().model_card().name == "pridict2"


def test_adapters_interface() -> None:
    assert DeepPrimeAdapter().name == "DeepPrime"
    with pytest.raises(Exception, match="no model card"):
        GenETAdapter().model_card()  # no 'genet' card is bundled
