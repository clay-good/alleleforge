"""Cas9 enumeration where the edit sits on the contig's first base.

Every Cas9 fixture in the suite put its variant comfortably mid-contig, so the clamps
that exist for the start of a reference were never reached: the fetched enumeration
window (`max(0, actionable.start - margin)`), the carried-allele overlay's lower bound
(`0 <= rel`, and `rel < 0` inside the overlay itself), and the two spans that reach
behind a guide for its PAM (`guide_context`, `_corrected_span`). Each could gain a base
with the suite green. A protospacer beginning at base 0 is dropped if the window starts
one base late, and an edit at base 0 is never installed if the overlay's lower bound is
exclusive — the guide would then be enumerated against a genome the target does not
carry, which is the one thing this module exists to avoid.
"""

from __future__ import annotations

from collections.abc import Callable

from alleleforge.enumerate.cas9 import enumerate_cas9, guide_context, hdr_donor
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent
from alleleforge.types.sequence import DNASequence, Strand
from alleleforge.variant.resolver import resolve

from .conftest import PAD, SPACER

MakeRef = Callable[[dict[str, str]], ReferenceGenome]

#: A contig whose plus protospacer occupies [0, 20) — its first base is base 0.
_AT_START = SPACER + "TGG" + PAD


def test_a_protospacer_on_the_first_base_is_enumerated(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": _AT_START})
    rv = resolve(f"chr2:1:{SPACER[0]}>G", reference=ref)
    assert rv.variant.pos == 0, "the fixture must sit on base 0 or it measures nothing"
    guides = enumerate_cas9(rv, EditIntent.CORRECT, reference=ref, actionable_radius=20)
    starts = {g.placement.start for g in guides if g.placement.strand is Strand.PLUS}
    assert 0 in starts, (
        "the guide whose protospacer starts at the contig's first base was dropped; "
        "the fetched window began one base late"
    )


def test_an_edit_on_the_first_base_is_carried_into_the_enumerated_guide(
    make_reference: MakeRef,
) -> None:
    """The overlay's lower bound is inclusive, so base 0 is a position it covers."""
    ref = make_reference({"chr2": _AT_START})
    rv = resolve(f"chr2:1:{SPACER[0]}>G", reference=ref)
    guides = enumerate_cas9(rv, EditIntent.CORRECT, reference=ref, actionable_radius=20)
    at_start = [g for g in guides if g.placement.start == 0]
    assert at_start, "no guide covers base 0; the rest of this test would measure nothing"
    # CORRECT means the target genome carries the alt and the donor restores the ref, so
    # the enumerated spacer must read the alt at its first base, never the reference's.
    assert {str(g.spacer.sequence)[0] for g in at_start} == {"G"}
    assert SPACER[0] != "G", "the fixture's ref and alt must differ at base 0"


def test_the_scored_context_of_a_guide_at_base_zero(make_reference: MakeRef) -> None:
    """A 5' flank that would reach before the contig is truncated, not shifted."""
    ref = make_reference({"chr2": _AT_START})
    rv = resolve(f"chr2:1:{SPACER[0]}>G", reference=ref)
    guide = next(
        g
        for g in enumerate_cas9(rv, EditIntent.CORRECT, reference=ref, actionable_radius=20)
        if g.placement.start == 0 and g.placement.strand is Strand.PLUS
    )
    overlay = (rv.variant.pos, rv.variant.ref, rv.variant.alt)
    ctx = guide_context(guide, ref, flank_5=6, flank_3=3, overlay=overlay)
    # There is nothing 5' of base 0: the context begins with the protospacer itself and
    # carries only the 3' flank, so the window is short by exactly the missing flank.
    assert ctx == "G" + SPACER[1:] + "TGG" + _AT_START[23:26]
    assert len(ctx) == 20 + 3 + 3


def test_a_minus_guide_at_base_zero_still_gets_its_donor(make_reference: MakeRef) -> None:
    """``_corrected_span`` reaches ``pam_len`` behind a minus guide — possibly past 0."""
    rc = str(DNASequence(SPACER).reverse_complement())
    ref = make_reference({"chr2": rc + PAD})  # minus protospacer at [0, 20), no PAM 5' of it
    rv = resolve("chr2:1:" + rc[0] + ">G", reference=ref)
    guides = enumerate_cas9(rv, EditIntent.KNOCK_OUT, reference=ref)
    assert not any(g.placement.start == 0 and g.placement.strand is Strand.MINUS for g in guides), (
        "a minus guide needs a CCN 5' of its protospacer; base 0 cannot carry one"
    )
    # The donor itself must still be buildable at base 0, with no left homology arm.
    donor = hdr_donor(rv, EditIntent.CORRECT, reference=ref, arm_length=5)
    assert donor is not None
    assert str(donor.sequence) == rv.variant.ref + rc[1:6], "left arm must clamp to empty"
    assert len(str(donor.sequence)) == 1 + 5
