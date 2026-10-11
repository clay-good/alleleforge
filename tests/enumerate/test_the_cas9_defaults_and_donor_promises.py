"""The Cas9 defaults, and the promises the emitted donor sequence itself must keep.

A constant-mutation sweep of ``enumerate/cas9.py`` could shift either advertised
default and the blocked donor's own bases with the suite green:

* ``DEFAULT_ACTIONABLE_RADIUS`` (10 bp) had no fixture on its edge — every test either
  passed an explicit radius or put its guide far inside or far outside the window — so
  a default of 11 would have admitted a cut the module documents as too distant for
  HDR, and nothing would have failed.
* ``DEFAULT_HDR_ARM`` (50 bp) is named in this module's own prose as the reach that can
  touch an assembly gap the guide never sees. The number and the sentence were free to
  disagree.
* ``guide_context``'s default symmetric flank (6 bp) was never exercised: every caller
  in the suite passes ``flank_5``/``flank_3``, and ``design`` passes the scorer's own
  window, so the fallback window an undeclared scorer reads was unmeasured.
* The blocked donor's sequence was asserted only at the blocked index. The splice that
  writes the base in, and the trial sequence the search judges the base against, could
  each lose or shift a base: the recorded mutation stayed right while the *shipped
  oligo* changed length. A donor's length is the one thing a vendor reads it by.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from alleleforge.enumerate.cas9 import (
    DEFAULT_ACTIONABLE_RADIUS,
    DEFAULT_HDR_ARM,
    enumerate_cas9,
    guide_context,
    hdr_donor,
)
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent
from alleleforge.types.guide import PAM
from alleleforge.types.sequence import Strand
from alleleforge.variant.resolver import resolve

from .conftest import PAD, SPACER

MakeRef = Callable[[dict[str, str]], ReferenceGenome]

#: The plus protospacer sits at [15, 35) with its TGG PAM at [35, 38); the cut is 32.
_CONTIG = PAD + SPACER + "TGG" + PAD
_CUT = 32


def test_the_default_actionable_radius_admits_a_cut_exactly_that_far(
    make_reference: MakeRef,
) -> None:
    ref = make_reference({"chr2": _CONTIG})
    inside = _CUT - DEFAULT_ACTIONABLE_RADIUS  # the edit exactly one radius 5' of the cut
    rv = resolve(f"chr2:{inside + 1}:{_CONTIG[inside]}>G", reference=ref)
    cuts = {g.cut_site for g in enumerate_cas9(rv, EditIntent.CORRECT, reference=ref)}
    assert _CUT in cuts, "a cut exactly one default radius from the edit is actionable"


def test_the_default_actionable_radius_refuses_one_base_further(
    make_reference: MakeRef,
) -> None:
    """The other side of the same edge: one base beyond the default is out of range."""
    ref = make_reference({"chr2": _CONTIG})
    outside = _CUT - DEFAULT_ACTIONABLE_RADIUS - 1
    rv = resolve(f"chr2:{outside + 1}:{_CONTIG[outside]}>G", reference=ref)
    cuts = {g.cut_site for g in enumerate_cas9(rv, EditIntent.CORRECT, reference=ref)}
    assert _CUT not in cuts, (
        f"a cut {DEFAULT_ACTIONABLE_RADIUS + 1} bp from the edit was admitted; the "
        "default radius is wider than the module documents"
    )


def test_the_default_homology_arm_is_the_reach_the_module_states() -> None:
    """The prose explaining why a gap matters names the arm length; bind the two."""
    source = Path(hdr_donor.__code__.co_filename).read_text(encoding="utf-8")
    assert f"its arms reach {DEFAULT_HDR_ARM} bp either side" in source, (
        "the donor's own explanation of its reach no longer names the shipped default"
    )


def test_the_default_homology_arm_sizes_an_unclamped_donor(make_reference: MakeRef) -> None:
    long_enough = "A" * (DEFAULT_HDR_ARM + 10) + SPACER + "TGG" + "A" * (DEFAULT_HDR_ARM + 10)
    ref = make_reference({"chr2": long_enough})
    pos = DEFAULT_HDR_ARM + 15
    rv = resolve(f"chr2:{pos + 1}:{long_enough[pos]}>G", reference=ref)
    donor = hdr_donor(rv, EditIntent.CORRECT, reference=ref)
    assert donor is not None
    assert len(str(donor.sequence)) == 2 * DEFAULT_HDR_ARM + 1


def test_the_default_context_flank_is_symmetric_and_six(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": _CONTIG})
    rv = resolve("chr2:40:T>A", reference=ref)  # past the PAM, so the spacer is untouched
    guide = next(
        g
        for g in enumerate_cas9(rv, EditIntent.KNOCK_OUT, reference=ref)
        if str(g.spacer.sequence) == SPACER and g.placement.strand is Strand.PLUS
    )
    ctx = guide_context(guide, ref)
    assert ctx == _CONTIG[9:44]
    assert len(ctx) == 6 + 20 + 3 + 6, "the default flank is 6 bp on each side"


def test_a_blocked_donor_is_the_unblocked_one_with_exactly_one_base_changed(
    make_reference: MakeRef,
) -> None:
    ref = make_reference({"chr2": _CONTIG})
    rv = resolve("chr2:25:T>A", reference=ref)  # PAM-distal: the PAM and seed survive
    guide = next(
        g
        for g in enumerate_cas9(rv, EditIntent.CORRECT, reference=ref)
        if g.placement.strand is Strand.PLUS and str(g.pam_sequence) == "TGG"
    )
    plain = hdr_donor(rv, EditIntent.CORRECT, reference=ref)
    blocked = hdr_donor(rv, EditIntent.CORRECT, reference=ref, guide=guide)
    assert plain is not None and blocked is not None
    mutation = blocked.blocking_mutation
    assert mutation is not None, "this fixture must find a block, or it measures nothing"
    a, b = str(plain.sequence), str(blocked.sequence)
    assert len(a) == len(b), "blocking a donor must not change the oligo's length"
    assert [i for i in range(len(a)) if a[i] != b[i]] == [
        mutation.position - max(0, rv.variant.pos - DEFAULT_HDR_ARM)
    ], "exactly one base changed, at the reported position"


def test_the_blocked_donors_pam_really_fails_to_match(make_reference: MakeRef) -> None:
    """The base is chosen by a trial sequence; judge the shipped donor, not the trial."""
    ref = make_reference({"chr2": _CONTIG})
    rv = resolve("chr2:25:T>A", reference=ref)
    guide = next(
        g
        for g in enumerate_cas9(rv, EditIntent.CORRECT, reference=ref)
        if g.placement.strand is Strand.PLUS and str(g.pam_sequence) == "TGG"
    )
    donor = hdr_donor(rv, EditIntent.CORRECT, reference=ref, guide=guide)
    assert donor is not None and donor.blocking_mutation is not None
    left_start = max(0, rv.variant.pos - DEFAULT_HDR_ARM)
    pam_in_donor = str(donor.sequence)[
        guide.placement.end - left_start : guide.placement.end - left_start + 3
    ]
    assert len(pam_in_donor) == 3, "the donor must span the PAM for this to mean anything"
    assert not PAM(pattern="NGG").matches(pam_in_donor), (
        f"the donor still presents a matching PAM ({pam_in_donor}); the repaired "
        "allele can be re-cut despite recut_blocked"
    )
    assert donor.recut_blocked is True


def test_no_block_available_is_reported_as_an_unblocked_donor(
    make_reference: MakeRef,
) -> None:
    """Arms too short to reach the PAM: the search runs, finds nothing, and says so."""
    ref = make_reference({"chr2": _CONTIG})
    rv = resolve("chr2:25:T>A", reference=ref)
    guide = next(
        g
        for g in enumerate_cas9(rv, EditIntent.CORRECT, reference=ref)
        if g.placement.strand is Strand.PLUS and str(g.pam_sequence) == "TGG"
    )
    donor = hdr_donor(rv, EditIntent.CORRECT, reference=ref, guide=guide, arm_length=5)
    assert donor is not None
    assert donor.blocking_mutation is None
    assert donor.recut_blocked is False, (
        "a search that ran and found nothing is False, not None and not True"
    )
    assert donor.note is not None and "no PAM-blocking mutation available" in donor.note
