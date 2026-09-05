"""Cas9 enumeration against a genome carrying a length-changing allele.

For a precise intent the target genome carries the *alternate* allele, and guides
must be enumerated against that sequence — not the reference. A length-changing
allele was previously skipped by the overlay, so a correcting design was silently
enumerated on the reference: it could propose a guide whose PAM the patient's own
deletion has removed (a reagent that cannot cut), and could miss the PAM the
deletion creates at the junction. These tests pin both directions.

The contigs are AT-only apart from the bases planted here, so the *only* NGG/CCN
PAMs in play are the ones each test puts there deliberately.
"""

from __future__ import annotations

from collections.abc import Callable

from alleleforge.enumerate.cas9 import enumerate_cas9, guide_context, hdr_donor
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand
from alleleforge.variant.resolver import resolve

MakeRef = Callable[[dict[str, str]], ReferenceGenome]

EDIT_POS = 100


def _filler() -> list[str]:
    """Return an AT-only contig: no NGG and no CCN anywhere."""
    return list("AT" * 100)


def test_a_pam_the_deletion_removes_is_not_designed(make_reference: MakeRef) -> None:
    seq = _filler()
    seq[EDIT_POS + 1 : EDIT_POS + 4] = list("TGG")  # the only PAM in the reference
    contig = "".join(seq)
    ref = make_reference({"chr1": contig})
    ref_allele = contig[EDIT_POS : EDIT_POS + 4]  # "ATGG"
    rv = resolve(f"chr1:{EDIT_POS + 1}:{ref_allele}>{ref_allele[0]}", reference=ref)
    assert rv.variant.pos == EDIT_POS

    # INSTALL: the genome still carries the reference, so the PAM is there.
    installing = enumerate_cas9(rv, EditIntent.INSTALL, reference=ref)
    assert installing, "the reference PAM must be designable while it still exists"

    # CORRECT: the genome carries the deletion, which has taken the PAM with it.
    # Designing this guide would hand the bench a reagent that cannot cut.
    assert enumerate_cas9(rv, EditIntent.CORRECT, reference=ref) == []


def test_a_pam_the_deletion_creates_is_found(make_reference: MakeRef) -> None:
    seq = _filler()
    seq[EDIT_POS - 1] = "C"  # a lone C: no CCN pair, and blocks left-alignment drift
    seq[EDIT_POS] = "G"  # the deletion's anchor base
    seq[EDIT_POS + 4] = "G"  # brought adjacent to the anchor once 3 bases are cut
    contig = "".join(seq)
    ref = make_reference({"chr1": contig})
    ref_allele = contig[EDIT_POS : EDIT_POS + 4]
    rv = resolve(f"chr1:{EDIT_POS + 1}:{ref_allele}>{ref_allele[0]}", reference=ref)
    assert rv.variant.pos == EDIT_POS

    # The reference has no PAM at all: nothing to design against it.
    assert enumerate_cas9(rv, EditIntent.INSTALL, reference=ref) == []

    # The patient's junction spells CGG. That guide is real and must be found.
    guides = enumerate_cas9(rv, EditIntent.CORRECT, reference=ref)
    assert guides
    patient = contig[:EDIT_POS] + ref_allele[0] + contig[EDIT_POS + len(ref_allele) :]
    for guide in guides:
        anchor = str(guide.spacer.sequence) + str(guide.pam_sequence)
        if guide.placement.strand is Strand.MINUS:
            anchor = str(
                DNASequence(
                    str(guide.spacer.sequence) + str(guide.pam_sequence)
                ).reverse_complement()
            )
        assert anchor in patient, "an emitted guide must exist in the genome it targets"


def test_placement_and_context_survive_the_length_change(make_reference: MakeRef) -> None:
    seq = _filler()
    seq[EDIT_POS - 1] = "C"
    seq[EDIT_POS] = "G"
    seq[EDIT_POS + 4] = "G"
    contig = "".join(seq)
    ref = make_reference({"chr1": contig})
    ref_allele = contig[EDIT_POS : EDIT_POS + 4]
    rv = resolve(f"chr1:{EDIT_POS + 1}:{ref_allele}>{ref_allele[0]}", reference=ref)
    guides = enumerate_cas9(rv, EditIntent.CORRECT, reference=ref)
    assert guides
    overlay = (rv.variant.pos, rv.variant.ref, rv.variant.alt)

    for guide in guides:
        placement = guide.placement
        # A protospacer 5' of the edit keeps an exact reference footprint.
        if placement.end <= rv.variant.pos:
            window = str(
                ref.fetch(
                    GenomicInterval(
                        chrom="chr1",
                        start=placement.start,
                        end=placement.end,
                        strand=Strand.PLUS,
                    )
                )
            )
            expected = str(guide.spacer.sequence)
            if placement.strand is Strand.MINUS:
                expected = str(DNASequence(expected).reverse_complement())
            assert window == expected

        # The scored context is the carried sequence and keeps its requested shape:
        # 4 nt 5' + 20 nt protospacer + 3 nt PAM + 3 nt 3' = the Rule Set 3 30-mer.
        ctx = guide_context(guide, ref, flank_5=4, flank_3=3, overlay=overlay)
        assert len(ctx) == 30
        assert str(guide.spacer.sequence) in ctx


def test_a_donor_reaching_an_assembly_gap_is_refused(make_reference: MakeRef) -> None:
    """A repair template's bases are written into the genome permanently.

    The enumerators skip any emitted span covering a reference `N`; a donor is the
    one reagent where an ambiguous base would be installed for good, and its
    homology arms reach 50 bp either side — far enough to touch a gap the guide
    never sees. Fail closed with no donor rather than build an unsynthesizable one.
    """
    seq = _filler()
    seq[EDIT_POS + 1 : EDIT_POS + 4] = list("TGG")
    seq[EDIT_POS + 30] = "N"  # inside the 50-bp right homology arm
    contig = "".join(seq)
    ref = make_reference({"chr1": contig})
    ref_allele = contig[EDIT_POS : EDIT_POS + 4]
    rv = resolve(f"chr1:{EDIT_POS + 1}:{ref_allele}>{ref_allele[0]}", reference=ref)

    guides = enumerate_cas9(rv, EditIntent.INSTALL, reference=ref)
    assert guides, "the guide itself is unaffected by a gap 30 bp away"
    for guide in guides:
        assert hdr_donor(rv, EditIntent.INSTALL, reference=ref, guide=guide) is None

    # Without the gap the same locus does yield a donor, so the guard is what
    # refuses it — not the locus being undesignable.
    clean = make_reference({"chr1": contig.replace("N", "A")})
    rv_clean = resolve(f"chr1:{EDIT_POS + 1}:{ref_allele}>{ref_allele[0]}", reference=clean)
    clean_guides = enumerate_cas9(rv_clean, EditIntent.INSTALL, reference=clean)
    assert any(
        hdr_donor(rv_clean, EditIntent.INSTALL, reference=clean, guide=g) is not None
        for g in clean_guides
    )
