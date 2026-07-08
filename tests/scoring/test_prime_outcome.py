"""Tests for prime-editing outcome (intended vs. byproduct) prediction."""

from __future__ import annotations

import math

from alleleforge.scoring.prime_outcome import PrimeOutcomePredictor
from alleleforge.types.guide import NickingGuide, PegRNA, Spacer, ThreePrimeMotif
from alleleforge.types.prediction import UncertaintyMethod
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand

_SCAFFOLD = DNASequence("GTTTTAGAGCTAGAAATAGCAAG")


def _ng(seed_disrupting: bool) -> NickingGuide:
    return NickingGuide(
        spacer=Spacer(sequence=DNASequence("ACGTACGTACGTACGTACGT")),
        placement=GenomicInterval(chrom="chr2", start=100, end=120, strand=Strand.MINUS),
        nick_offset=50,
        seed_disrupting=seed_disrupting,
    )


def _peg(
    *,
    rtt: str = "ACGTACGTACGTACGT",
    motif: ThreePrimeMotif = ThreePrimeMotif.TEVOPREQ1,
    ng: NickingGuide | None = None,
) -> PegRNA:
    return PegRNA(
        spacer=Spacer(sequence=DNASequence("ACGTACGTACGTACGTACGT")),
        scaffold=_SCAFFOLD,
        rtt=DNASequence(rtt),
        pbs=DNASequence("ACGTACGTACGTA"),
        three_prime_motif=motif,
        rtt_homology_3prime=5,
        nicking_guide=ng,
    )


def test_distribution_normalized() -> None:
    result = PrimeOutcomePredictor().predict(_peg())
    assert math.isclose(sum(a.probability for a in result.outcome.alleles), 1.0, abs_tol=1e-9)
    assert result.p_intended.method is UncertaintyMethod.HEURISTIC


def test_intended_marked_and_byproducts_present() -> None:
    result = PrimeOutcomePredictor().predict(_peg())
    alleles = {a.allele for a in result.outcome.alleles}
    assert "intended" in alleles
    assert {"scaffold_incorporation", "partial_rtt", "indel"} <= alleles
    intended = [a for a in result.outcome.alleles if a.is_intended]
    assert len(intended) == 1 and intended[0].allele == "intended"


def test_outcome_flags_ood_on_ambiguous_reagent() -> None:
    # The OOD flag is computed from the reagent sequence, not hardcoded: a clean
    # pegRNA is in-distribution; an ambiguous base (N) in the RTT flags it OOD.
    assert PrimeOutcomePredictor().predict(_peg()).p_intended.in_distribution is True
    dirty = PrimeOutcomePredictor().predict(_peg(rtt="ACGTNCGTACGTACGT"))
    assert dirty.p_intended.in_distribution is False


def test_pe3b_suppresses_indels() -> None:
    pe3b = PrimeOutcomePredictor().predict(_peg(ng=_ng(seed_disrupting=True)))
    pe3 = PrimeOutcomePredictor().predict(_peg(ng=_ng(seed_disrupting=False)))
    indel_pe3b = next(a.probability for a in pe3b.outcome.alleles if a.allele == "indel")
    indel_pe3 = next(a.probability for a in pe3.outcome.alleles if a.allele == "indel")
    assert indel_pe3b < indel_pe3


def test_epegrna_reduces_scaffold_incorporation() -> None:
    epeg = PrimeOutcomePredictor().predict(_peg(motif=ThreePrimeMotif.TEVOPREQ1))
    plain = PrimeOutcomePredictor().predict(_peg(motif=ThreePrimeMotif.NONE))
    s_epeg = next(
        a.probability for a in epeg.outcome.alleles if a.allele == "scaffold_incorporation"
    )
    s_plain = next(
        a.probability for a in plain.outcome.alleles if a.allele == "scaffold_incorporation"
    )
    assert s_epeg < s_plain


def test_long_rtt_raises_byproducts() -> None:
    short = PrimeOutcomePredictor().predict(_peg(rtt="ACGTACGTACGT"))  # 12
    long = PrimeOutcomePredictor().predict(_peg(rtt="ACGTACGTACGTACGTACGTACGTACGTACGT"))  # 32
    assert short.p_intended.value > long.p_intended.value
