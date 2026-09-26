"""Tests for prime-editing outcome (intended vs. byproduct) prediction."""

from __future__ import annotations

import math

import pytest

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


# -- the two byproduct terms that RTT length actually moves ---------------------
#
# The byproduct mix is three propensities from pegRNA geometry, and two of them depend on
# RTT length in different ways: scaffold incorporation is flat until 20 nt and then climbs
# (`0.10 + 0.01 * max(0, rtt_len - 20)`, "long RTTs read into scaffold"), while partial
# reverse transcription climbs throughout (`0.08 + 0.004 * rtt_len`). Every fixture used a
# single RTT length, so neither shape was measured: the hinge sat at zero and the linear
# term was a constant.


def _mass(rtt_len: int, allele: str) -> float:
    """The probability of one byproduct allele for an otherwise-default pegRNA."""
    outcome = PrimeOutcomePredictor().predict(_peg(rtt="A" * rtt_len)).outcome
    return next(a.probability for a in outcome.alleles if a.allele == allele)


def test_scaffold_incorporation_is_flat_until_the_rtt_passes_twenty() -> None:
    """`0.10 + 0.01 * max(0, rtt_len - 20)` — a hinge, not a slope.

    With `min` in place of `max` the term goes *negative* below 20, so a short RTT is
    credited with less scaffold incorporation than the floor the literature figure sets;
    with the subtraction reversed it climbs from the shortest RTT instead of from 20. Both
    read as a plausible byproduct mix, and both misattribute the mass that decides
    `p_intended`.
    """
    flat = {_mass(n, "scaffold_incorporation") for n in (7, 12, 16, 20)}
    assert flat == {0.10}, f"scaffold must sit at its floor up to 20 nt, got {flat}"

    assert _mass(24, "scaffold_incorporation") == pytest.approx(0.14)
    assert _mass(30, "scaffold_incorporation") == pytest.approx(0.20)


def test_partial_reverse_transcription_climbs_with_every_added_base() -> None:
    """`0.08 + 0.004 * rtt_len` — linear in length, with no hinge.

    This is the term that distinguishes a 12-nt RTT from a 20-nt one, where scaffold
    incorporation cannot. Dividing by the length instead of multiplying makes longer RTTs
    stop early *less* often, which inverts the documented behaviour.
    """
    masses = [_mass(n, "partial_rtt") for n in (7, 12, 16, 20, 24, 30)]
    assert masses == sorted(masses), "a longer RTT must stop early more often"
    assert masses[0] < masses[-1]
    assert _mass(20, "partial_rtt") == pytest.approx(0.16)


def test_a_longer_rtt_lowers_the_intended_probability_throughout() -> None:
    """The two terms together, as the caller sees them.

    Below the hinge only partial-RTT moves; above it both do. `p_intended` must therefore
    fall across the whole range, and fall faster past 20 nt.
    """
    p = {n: _mass(n, "intended") for n in (12, 16, 20, 24, 30)}
    assert list(p.values()) == sorted(p.values(), reverse=True)
    below = p[16] - p[20]
    above = p[20] - p[24]
    assert above > below, "past the hinge both terms add, so the fall steepens"
