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


def _context(cca_start: int = 58) -> str:
    # AT-only fill has no GG/CC, so the only PAMs are the ones we insert:
    #   a plus pegRNA PAM (TGG) whose nick sits 10 nt 5' of the edit at 70, and
    #   a minus ngRNA PAM (CCA -> NGG on the minus strand). The ngRNA protospacer
    #   reads on the minus strand, so its PAM-proximal seed end is the LOW genomic
    #   boundary proto_lo = cca_start + 3. Default cca_start=58 -> proto_lo=61, seed
    #   [61, 71) which spans the edit at 70 (a genuine PE3b). cca_start=55 ->
    #   proto_lo=58, so edit 70 is 12 nt away, in the PAM-distal half (not PE3b).
    seq = list("AT" * 70)  # length 140
    seq[63:66] = list("TGG")  # plus pegRNA PAM; nick = 63 - 3 = 60
    seq[cca_start : cca_start + 3] = list("CCA")  # minus ngRNA PAM
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


def test_rtt_never_spans_an_assembly_gap_n(make_reference: MakeRef) -> None:
    # The RT template is synthesized DNA: it must be concrete A/C/G/T, exactly like the
    # spacer and the nicking-guide protospacer (both N-guarded). A pegRNA whose RTT window
    # reaches a downstream reference 'N' (assembly gap) is an unsynthesizable oligo that
    # would template an ambiguous base into the genome at the gap. The enumerator must skip
    # it, mirroring the cas9/base-editor per-span N-guards. `DNASequence` permits IUPAC 'N'
    # (needed for degenerate PAMs), so PegRNA construction never caught this.
    ctx = "A" * 24 + "GG" + "A" * 7 + "N" + "A" * 55  # PAM 'AGG' at [23,26); gap N at pos 33
    ref = make_reference({"chr1": ctx})
    rv = resolve("chr1:21:A>C", reference=ref)  # A>C at 0-based 20 (CORRECT)
    pegs = enumerate_prime(rv, EditIntent.CORRECT, reference=ref)
    assert pegs  # the shorter RTTs that stop before the gap still resolve
    assert all("N" not in str(p.rtt) for p in pegs)


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
    # The ngRNA's PAM-proximal seed [61, 71) spans the edit at 70, so this is a
    # genuine PE3b (measured from proto_lo, the minus-strand PAM-proximal end).
    _ref, pegs = _pegs(make_reference)
    plus = next(p for p in pegs if p.placement.strand is Strand.PLUS)
    assert plus.nicking_guide is not None
    assert plus.nicking_guide.seed_disrupting


def test_pe3b_spacer_is_templated_from_the_edited_strand(make_reference: MakeRef) -> None:
    # PE3b's whole benefit is nicking ONLY the edited strand: the emitted ngRNA
    # spacer must match the EDITED allele (seed-matches the product, mismatches the
    # original). Templating it from the unedited allele nicks the original molecule
    # and fails on the product — the exact inverse of the guarantee.
    ref, pegs = _pegs(make_reference, alt="C")
    seq = str(ref.fetch(GenomicInterval(chrom="chr2", start=0, end=140, strand=Strand.PLUS)))
    edited = seq[:70] + "C" + seq[71:]
    plus = next(p for p in pegs if p.placement.strand is Strand.PLUS)
    ng = plus.nicking_guide
    assert ng is not None and ng.seed_disrupting
    lo, hi = ng.placement.start, ng.placement.end
    edited_spacer = str(DNASequence(edited[lo:hi]).reverse_complement())
    original_spacer = str(DNASequence(seq[lo:hi]).reverse_complement())
    assert str(ng.spacer.sequence) == edited_spacer  # matches the edited strand
    assert str(ng.spacer.sequence) != original_spacer  # NOT the unedited allele


def test_pam_distal_edit_is_not_labeled_pe3b(make_reference: MakeRef) -> None:
    # With the ngRNA PAM one codon further 5' (proto_lo=58), the edit at 70 is 12 nt
    # away — in the PAM-DISTAL half, not the seed. The prior code measured the seed
    # from proto_hi and would falsely promote this to PE3b; the corrected code does
    # not, so no seed-disrupting nicking guide is emitted here.
    ref = make_reference({"chr2": _context(cca_start=55)})
    rv = _resolve(ref, 70, "C")
    pegs = enumerate_prime(rv, EditIntent.INSTALL, reference=ref)
    plus = next(p for p in pegs if p.placement.strand is Strand.PLUS)
    assert plus.nicking_guide is None or not plus.nicking_guide.seed_disrupting


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


def test_empty_pbs_lengths_returns_empty_not_crash(make_reference: MakeRef) -> None:
    # The margin max()es over pbs_lengths (and rtt_homologies); an empty pbs set
    # must degrade to an empty result, not raise on an empty max() — matching the
    # guarded rtt_homologies path.
    ref = make_reference({"chr2": _context()})
    rv = _resolve(ref, 70, "C")
    assert enumerate_prime(rv, EditIntent.INSTALL, reference=ref, pbs_lengths=()) == []


def test_pol3_terminator_spacer_is_filtered(make_reference: MakeRef) -> None:
    # A run of T's (a Pol III terminator) in the protospacer makes the pegRNA
    # untranscribable from a U6 promoter, so such a spacer must never be enumerated.
    _ref, baseline = _pegs(make_reference)
    assert any(p.placement.strand is Strand.PLUS for p in baseline)  # plus normally enumerates
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    seq[50:54] = list("TTTT")  # a terminator inside the plus protospacer window
    ref = make_reference({"chr2": "".join(seq)})
    rv = _resolve(ref, 70, "C")
    pegs = enumerate_prime(rv, EditIntent.INSTALL, reference=ref)
    assert all("TTTT" not in str(p.spacer.sequence) for p in pegs)
    # the plus candidate, whose protospacer holds the terminator, is filtered out
    assert all(p.placement.strand is not Strand.PLUS for p in pegs)
