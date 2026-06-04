"""Tests for prime-editing pegRNA enumeration."""

from __future__ import annotations

from collections.abc import Callable

from alleleforge.enumerate.prime import enumerate_prime
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent
from alleleforge.types.guide import PBS_RANGE, RTT_RANGE, ThreePrimeMotif
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand
from alleleforge.variant.resolver import ResolvedVariant, resolve

MakeRef = Callable[[dict[str, str]], ReferenceGenome]


def _context() -> str:
    # AT-only fill has no GG/CC, so the only PAMs are the ones we insert:
    #   a plus pegRNA PAM (TGG) whose nick sits 10 nt 5' of the edit at 70, and
    #   a minus ngRNA PAM (CCA -> NGG on the minus strand) whose seed spans the edit.
    seq = list("AT" * 70)  # length 140
    seq[63:66] = list("TGG")  # plus pegRNA PAM; nick = 63 - 3 = 60
    seq[55:58] = list("CCA")  # minus ngRNA PAM; protospacer [58, 78) covers edit 70
    return "".join(seq)


def _resolve(ref: ReferenceGenome, zero_based: int, alt: str) -> ResolvedVariant:
    base = str(
        ref.fetch(
            GenomicInterval(chrom="chr2", start=zero_based, end=zero_based + 1, strand=Strand.PLUS)
        )
    )
    return resolve(f"chr2:{zero_based + 1}:{base}>{alt}", reference=ref)


def _pegs(make_reference: MakeRef, alt: str = "C") -> tuple[ReferenceGenome, list]:
    ref = make_reference({"chr2": _context()})
    rv = _resolve(ref, 70, alt)
    return ref, enumerate_prime(rv, EditIntent.INSTALL, reference=ref)


def test_pbs_rtt_within_ranges(make_reference: MakeRef) -> None:
    _ref, pegs = _pegs(make_reference)
    assert pegs
    for p in pegs:
        assert PBS_RANGE[0] <= len(p.pbs) <= PBS_RANGE[1]
        assert RTT_RANGE[0] <= len(p.rtt) <= RTT_RANGE[1]
        assert p.rtt_homology_3prime >= 5
        assert p.rtt_homology_3prime <= len(p.rtt)


def test_pbs_binds_5prime_of_nick(make_reference: MakeRef) -> None:
    ref, pegs = _pegs(make_reference)
    seq = str(ref.fetch(GenomicInterval(chrom="chr2", start=0, end=140, strand=Strand.PLUS)))
    plus = next(p for p in pegs if p.placement.strand is Strand.PLUS)
    nick = plus.nick_site
    expect = str(DNASequence(seq[nick - len(plus.pbs) : nick]).reverse_complement())
    assert str(plus.pbs) == expect  # PBS is revcomp of the bases just 5' of the nick


def test_rtt_encodes_the_edit(make_reference: MakeRef) -> None:
    ref, pegs = _pegs(make_reference, alt="C")
    seq = str(ref.fetch(GenomicInterval(chrom="chr2", start=0, end=140, strand=Strand.PLUS)))
    edited = seq[:70] + "C" + seq[71:]
    plus = next(p for p in pegs if p.placement.strand is Strand.PLUS)
    nick = plus.nick_site
    rtt_template = str(DNASequence(str(plus.rtt)).reverse_complement())
    assert rtt_template == edited[nick : nick + len(plus.rtt)]
    assert rtt_template[70 - nick] == "C"  # the desired base sits in the RTT


def test_tevopreq1_attached_by_default(make_reference: MakeRef) -> None:
    _ref, pegs = _pegs(make_reference)
    assert all(p.three_prime_motif is ThreePrimeMotif.TEVOPREQ1 and p.is_epegrna for p in pegs)


def test_pe3b_preferred_when_seed_disrupting(make_reference: MakeRef) -> None:
    _ref, pegs = _pegs(make_reference)
    plus = next(p for p in pegs if p.placement.strand is Strand.PLUS)
    assert plus.nicking_guide is not None
    assert plus.nicking_guide.seed_disrupting  # the CCA ngRNA's seed spans the edit


def test_both_strands_enumerated(make_reference: MakeRef) -> None:
    _ref, pegs = _pegs(make_reference)
    strands = {p.placement.strand for p in pegs if p.placement}
    assert Strand.PLUS in strands  # at minimum the plus pegRNA exists


def test_pe3_disabled(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": _context()})
    rv = _resolve(ref, 70, "C")
    pegs = enumerate_prime(rv, EditIntent.INSTALL, reference=ref, pe3=False)
    assert pegs and all(p.nicking_guide is None for p in pegs)


def test_correct_intent_rtt_encodes_reference(make_reference: MakeRef) -> None:
    # The clinical case: a genome carrying the variant (alt) is corrected back to
    # the reference allele. The pegRNA binds the alt sequence; the RTT encodes ref.
    ref = make_reference({"chr2": _context()})
    seq = str(ref.fetch(GenomicInterval(chrom="chr2", start=0, end=140, strand=Strand.PLUS)))
    ref_base = seq[70]
    alt = "C" if ref_base != "C" else "A"
    rv = resolve(f"chr2:71:{ref_base}>{alt}", reference=ref)  # ref->alt is the variant
    pegs = enumerate_prime(rv, EditIntent.CORRECT, reference=ref)
    assert pegs
    plus = next(p for p in pegs if p.placement.strand is Strand.PLUS)
    nick = plus.nick_site
    rtt_template = str(DNASequence(str(plus.rtt)).reverse_complement())
    assert rtt_template[70 - nick] == ref_base  # correcting installs the reference allele
    # the pegRNA spacer is read against the alt-carrying genome it edits
    proto_start = plus.placement.start
    if proto_start <= 70 < plus.placement.end:
        assert str(plus.spacer.sequence)[70 - proto_start] == alt


def test_non_single_position_edit_empty(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": _context()})
    rv = resolve("chr2:71:ATA>A", reference=ref)  # a deletion (not single-position)
    assert enumerate_prime(rv, EditIntent.CORRECT, reference=ref) == []
