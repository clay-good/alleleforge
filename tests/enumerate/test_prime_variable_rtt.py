"""Metamorphic verification of the variable-length RTT path.

Prime editing's whole value is that it writes an *arbitrary* small edit. These
tests fetch every enumerated pegRNA back against the genome it is meant to act
on and prove the reagent really installs the intended edit — for substitutions,
MNVs, insertions, deletions, and delins alike.

The oracle is deliberately independent of the enumerator's own arithmetic: it
takes only the emitted PBS/RTT/spacer sequences, locates the reverse-transcribed
product in the **edited** genome by content, and checks that the same locus in
the **start** genome carries the PBS and the protospacer. A pegRNA that templated
the wrong bases, reached the wrong locus, or stopped short of the edit fails.
"""

from __future__ import annotations

import random
from collections.abc import Callable

import pytest

from alleleforge.enumerate.prime import (
    DEFAULT_CUT_OFFSET,
    NGG_PAM,
    PRIME_MAX_TEMPLATED_EDIT,
    enumerate_prime,
)
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent
from alleleforge.types.guide import (
    DEFAULT_SPACER_LENGTH,
    MIN_RTT_3PRIME_HOMOLOGY,
    PegRNA,
)
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand
from alleleforge.types.variant import Variant
from alleleforge.variant.resolver import ResolvedVariant, resolve

MakeRef = Callable[[dict[str, str]], ReferenceGenome]

#: Where every test variant sits in the synthetic contig.
EDIT_POS = 200


def _rc(seq: str) -> str:
    return str(DNASequence(seq).reverse_complement())


def _contig(seed: int = 20260909, length: int = 420) -> str:
    """Return a high-complexity contig: real PAMs, near-unique substrings."""
    rng = random.Random(seed)
    return "".join(rng.choice("ACGT") for _ in range(length))


#: ``(label, ref, alt)`` triples covering the whole small-edit repertoire. ``ref``
#: is overlaid onto the contig at :data:`EDIT_POS` so the assertion always holds.
CASES = [
    ("snv", "A", "G"),
    ("mnv", "ACG", "TTA"),
    ("insertion", "A", "AGGCT"),
    ("deletion", "ACGTA", "A"),
    ("delins", "ACGT", "TT"),
    ("large_deletion", "A" + "CGTACGTACGTACGTACGTA", "A"),
]


def _genomes(ref_allele: str, alt_allele: str) -> tuple[str, str, str]:
    """Return ``(reference contig, plus-strand ref allele, contig)`` with the ref planted."""
    base = _contig()
    contig = base[:EDIT_POS] + ref_allele + base[EDIT_POS + len(ref_allele) :]
    return contig, ref_allele, alt_allele


def _check_product(
    peg: PegRNA,
    *,
    start_genome: str,
    edited_genome: str,
    edit_lo: int,
    edit_hi: int,
) -> None:
    """Assert one pegRNA's RT product really writes the edit into the genome.

    ``edit_lo``/``edit_hi`` bound the edited allele in the plus-strand *edited*
    genome (equal for a pure deletion).
    """
    strand = peg.placement.strand if peg.placement is not None else Strand.PLUS
    # Work in the pegRNA's own frame: the minus-strand reagent reads the reverse
    # complement of both genomes, with coordinates mirrored.
    if strand is Strand.MINUS:
        start_f, edited_f = _rc(start_genome), _rc(edited_genome)
        edit_lo_f, edit_hi_f = len(edited_genome) - edit_hi, len(edited_genome) - edit_lo
    else:
        start_f, edited_f = start_genome, edited_genome
        edit_lo_f, edit_hi_f = edit_lo, edit_hi
    pbs_template = _rc(str(peg.pbs))
    rtt_template = _rc(str(peg.rtt))
    product = pbs_template + rtt_template

    # 1. The RT product must exist, verbatim and uniquely, in the EDITED genome.
    assert edited_f.count(product) == 1, "RT product is not a unique locus of the edited genome"
    at = edited_f.index(product)

    # 2. The PBS half must anneal at that same locus in the START genome: it is
    #    5' of the nick, where the two genomes agree, so the primer binds before
    #    the edit exists.
    assert start_f[at : at + len(peg.pbs)] == pbs_template

    nick = at + len(peg.pbs)

    # 3. The protospacer must read off the START genome ending ``cut_offset``
    #    past the nick, with a real NGG PAM immediately 3' of it.
    proto_lo = nick - (DEFAULT_SPACER_LENGTH - DEFAULT_CUT_OFFSET)
    proto_hi = proto_lo + DEFAULT_SPACER_LENGTH
    assert start_f[proto_lo:proto_hi] == str(peg.spacer.sequence)
    assert NGG_PAM.matches(start_f[proto_hi : proto_hi + 3])

    # 4. The template must actually span the edit and carry real 3' homology past it.
    assert nick <= edit_lo_f, "nick must sit 5' of the edit"
    assert nick + len(peg.rtt) >= edit_hi_f + MIN_RTT_3PRIME_HOMOLOGY


@pytest.mark.parametrize(("label", "ref_allele", "alt_allele"), CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("intent", [EditIntent.CORRECT, EditIntent.INSTALL])
def test_rt_product_installs_the_intended_edit(
    make_reference: MakeRef, label: str, ref_allele: str, alt_allele: str, intent: EditIntent
) -> None:
    contig, _r, _a = _genomes(ref_allele, alt_allele)
    ref = make_reference({"chr1": contig})
    rv = resolve(f"chr1:{EDIT_POS + 1}:{ref_allele}>{alt_allele}", reference=ref)
    var = rv.variant
    pegs = enumerate_prime(rv, intent, reference=ref)
    assert pegs, f"{label}/{intent.value} enumerated nothing"

    # The genome the reagent acts on, and the genome it must produce.
    correcting = intent in (EditIntent.CORRECT, EditIntent.REVERT)
    carried, desired = (var.alt, var.ref) if correcting else (var.ref, var.alt)
    prefix, suffix = contig[: var.pos], contig[var.pos + len(var.ref) :]
    start_genome = prefix + carried + suffix
    edited_genome = prefix + desired + suffix
    assert start_genome != edited_genome

    for peg in pegs:
        _check_product(
            peg,
            start_genome=start_genome,
            edited_genome=edited_genome,
            edit_lo=var.pos,
            edit_hi=var.pos + len(desired),
        )


@pytest.mark.parametrize(("label", "ref_allele", "alt_allele"), CASES, ids=[c[0] for c in CASES])
def test_both_strands_are_enumerated(
    make_reference: MakeRef, label: str, ref_allele: str, alt_allele: str
) -> None:
    contig, _r, _a = _genomes(ref_allele, alt_allele)
    ref = make_reference({"chr1": contig})
    rv = resolve(f"chr1:{EDIT_POS + 1}:{ref_allele}>{alt_allele}", reference=ref)
    pegs = enumerate_prime(rv, EditIntent.INSTALL, reference=ref)
    strands = {p.placement.strand for p in pegs if p.placement is not None}
    assert strands == {Strand.PLUS, Strand.MINUS}, f"{label} missed a strand: {strands}"


def test_deletion_rtt_is_shorter_than_the_span_it_removes(make_reference: MakeRef) -> None:
    """A deleted span costs no RT template — that is why big deletions are cheap."""
    ref_allele = "AGCTAGCTTGACCATGGTCA"  # 19 bases removed; no rolling repeat unit
    contig, _r, _a = _genomes(ref_allele, "A")
    # A PAM ending just 5' of the edit, so a short-distance pegRNA is guaranteed.
    contig = contig[: EDIT_POS - 3] + "TGG" + contig[EDIT_POS:]
    ref = make_reference({"chr1": contig})
    rv = resolve(f"chr1:{EDIT_POS + 1}:{ref_allele}>A", reference=ref)
    pegs = enumerate_prime(rv, EditIntent.INSTALL, reference=ref)
    assert pegs
    # 19 bases are removed; the RTT never has to carry them.
    assert min(len(p.rtt) for p in pegs) < len(ref_allele) - 1


def test_untemplatable_insertion_is_refused(make_reference: MakeRef) -> None:
    """An allele too long for any in-range RTT is declined, not half-enumerated."""
    contig, _r, _a = _genomes("A", "A")
    ref = make_reference({"chr1": contig})
    long_alt = "A" + "CGTA" * 9  # 37 templated bases > PRIME_MAX_TEMPLATED_EDIT (29)
    assert len(long_alt) > PRIME_MAX_TEMPLATED_EDIT
    rv = resolve(f"chr1:{EDIT_POS + 1}:A>{long_alt}", reference=ref)
    assert enumerate_prime(rv, EditIntent.INSTALL, reference=ref) == []
    # ...but correcting it (writing the single reference base back) is templatable.
    assert enumerate_prime(rv, EditIntent.CORRECT, reference=ref)


def test_placement_is_the_reference_footprint(make_reference: MakeRef) -> None:
    """A placement must fetch back to the protospacer it claims (or be honest).

    For a spacer 5' of the edit the footprint is exact. For one spanning a
    deletion the reference footprint is *wider* than the 20 nt spacer, because
    the patient's 20 bases derive from more reference bases — reporting the
    spacer's own length there would name a locus the bases do not come from.
    """
    ref_allele = "ATTGC"
    contig, _r, _a = _genomes(ref_allele, "A")
    # In the CORRECT frame the genome carries only the anchor base, so plant a PAM
    # whose protospacer runs across the edit point: it must fetch back to a *wider*
    # reference footprint than its own 20 nt.
    contig = contig[: EDIT_POS + len(ref_allele)] + "TGG" + contig[EDIT_POS + len(ref_allele) + 3 :]
    ref = make_reference({"chr1": contig})
    rv = resolve(f"chr1:{EDIT_POS + 1}:{ref_allele}>A", reference=ref)
    var = rv.variant
    assert var.pos == EDIT_POS and var.ref == ref_allele
    # CORRECT: the genome carries the 4-bp deletion; we write the reference back.
    pegs = enumerate_prime(rv, EditIntent.CORRECT, reference=ref)
    assert pegs
    spanning = 0
    for peg in pegs:
        assert peg.placement is not None
        window = contig[peg.placement.start : peg.placement.end]
        expected = str(peg.spacer.sequence)
        if peg.placement.strand is Strand.MINUS:
            window = _rc(window)
        if len(window) == len(expected):
            assert window == expected  # does not cross the edit: exact fetch-back
        else:
            spanning += 1
            deleted = len(var.ref) - len(var.alt)
            assert len(window) == len(expected) + deleted
    assert spanning, "expected at least one deletion-spanning protospacer"


def _resolved(ref_allele: str, alt_allele: str, contig: str) -> ResolvedVariant:
    var = Variant(chrom="chr1", pos=EDIT_POS, ref=ref_allele, alt=alt_allele)
    window = GenomicInterval(
        chrom="chr1", start=EDIT_POS - 100, end=EDIT_POS + 100, strand=Strand.PLUS
    )
    assert contig[EDIT_POS : EDIT_POS + len(ref_allele)] == ref_allele
    return ResolvedVariant(variant=var, working_interval=window, source="test")


def test_no_op_edit_is_refused(make_reference: MakeRef) -> None:
    """An edit that writes what is already there is not a design; it is a no-op."""
    contig, _r, _a = _genomes("AC", "AC")
    ref = make_reference({"chr1": contig})
    rv = _resolved("AC", "AC", contig)
    assert enumerate_prime(rv, EditIntent.CORRECT, reference=ref) == []


def test_span_beyond_the_practical_limit_is_refused(make_reference: MakeRef) -> None:
    """A replaced span past PRIME_MAX_EDIT belongs to nuclease+HDR, not prime."""
    long_ref = "A" + "CGTA" * 12  # 49 bp > PRIME_MAX_EDIT (44)
    contig, _r, _a = _genomes(long_ref, "A")
    ref = make_reference({"chr1": contig})
    rv = _resolved(long_ref, "A", contig)
    assert enumerate_prime(rv, EditIntent.INSTALL, reference=ref) == []


def test_no_nicking_guide_is_placed_on_a_locus_it_does_not_occupy(
    make_reference: MakeRef,
) -> None:
    """A protospacer inside carried insertion has no reference locus — so no ngRNA.

    Correcting a large insertion means the target genome holds bases the reference
    does not. An ngRNA protospacer lying wholly inside them has a zero-width
    reference footprint; the enumerator must drop it rather than report a locus
    the reagent does not occupy.
    """
    insertion = "A" + "CC" + "TAGCATGCAAGCTTGCATGCA"  # carries a minus-strand PAM
    contig, _r, _a = _genomes("A", insertion)
    ref = make_reference({"chr1": contig})
    rv = _resolved("A", insertion, contig)
    pegs = enumerate_prime(rv, EditIntent.CORRECT, reference=ref)
    assert pegs
    for peg in pegs:
        if peg.nicking_guide is not None:
            placement = peg.nicking_guide.placement
            assert placement.end > placement.start
