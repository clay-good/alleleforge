"""The coordinate the Cas-OFFinder cross-check keys on, checked against the sequence.

`CasOffinderAdapter.reference_loci` shifts a minus-strand locus down by the PAM length,
because AlleleForge records the *protospacer* start while Cas-OFFinder reports the
leftmost coordinate of the whole protospacer+PAM match — and on the minus strand the PAM
sits at the low-coordinate end. Get that wrong and every minus-strand site raises a
spurious two-way disagreement, which is the failure mode of a tool whose entire job is
saying "these two engines disagree".

It was tested only against hand-written loci: a site built in the test with `start=1000`
and the assertion that 997 comes out. That checks the arithmetic against itself. It does
not check that 997 is where the match *is*, and it never sees a site the engine actually
produced — so a bulged alignment, whose protospacer is 21 or 19 bases rather than 20, was
outside it entirely.

The binary is not installable here, so parity against real Cas-OFFinder output stays out
of reach and is not faked. But the property that parity *depends on* is checkable without
it, from the reference itself: at the coordinate `reference_loci` reports, the bases must
actually be the match — the PAM at the 3' end of the protospacer as read on that site's
strand. That is ground truth from the FASTA, not a restatement of the shift.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.cas_offinder_adapter import CasOffinderAdapter
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM
from alleleforge.types.offtarget import SiteOrigin
from alleleforge.types.sequence import Strand, reverse_complement

_SPACER = "GACCATGCAACCTTGAACGT"
_PAM = PAM(pattern="NGG")
_PAM_LEN = 3


@pytest.fixture
def planted(tmp_path: Path) -> tuple[ReferenceGenome, str]:
    """A contig carrying the on-target and three relatives, on both strands.

    Deliberately not all plus-strand and not all 20 nt: the minus-strand shift is the
    thing under test, and a bulged alignment is the case the hand-written tests could
    not reach.
    """
    rng = random.Random(4)
    filler = lambda n: "".join(rng.choice("ACGT") for _ in range(n))  # noqa: E731
    sequence = (
        filler(300)
        + _SPACER
        + "TGG"  # exact, plus strand
        + filler(300)
        + reverse_complement("TGG")
        + reverse_complement(_SPACER[:-1] + "A")  # one mismatch, minus strand
        + filler(300)
        + _SPACER[:-2]
        + "AA"
        + "AGG"  # two mismatches, plus strand
        + filler(300)
    )
    fasta = tmp_path / "chr1.fa"
    fasta.write_text(f">chr1\n{sequence}\n")
    return ReferenceGenome(fasta, build="hg38"), sequence


def test_the_fixture_produces_sites_on_both_strands(planted: tuple[ReferenceGenome, str]) -> None:
    """Both halves of the check must be live, or the shift is never exercised."""
    reference, _ = planted
    report = search(_SPACER, _PAM, reference=reference)
    strands = {site.locus.strand for site in report.sites}
    assert strands == {Strand.PLUS, Strand.MINUS}, strands
    lengths = {len(site.locus) for site in report.sites}
    assert len(lengths) > 1, f"every protospacer is {lengths} — no bulged site to check"


def test_every_reported_anchor_is_where_the_match_actually_is(
    planted: tuple[ReferenceGenome, str],
) -> None:
    """Ground truth from the FASTA: read the bases at the anchor and confirm the match."""
    reference, sequence = planted
    report = search(_SPACER, _PAM, reference=reference)
    loci = CasOffinderAdapter.reference_loci(report)
    assert loci, "no reference-origin loci; the check would be vacuous"

    for site in report.sites:
        if site.origin is not SiteOrigin.REFERENCE:
            continue
        locus = site.locus
        anchor = locus.start - _PAM_LEN if locus.strand is Strand.MINUS else locus.start
        assert (locus.chrom, anchor, locus.strand) in loci, (locus, anchor)

        whole = (
            sequence[anchor : locus.end + _PAM_LEN]
            if locus.strand is Strand.PLUS
            else (sequence[anchor : locus.end])
        )
        assert len(whole) == len(locus) + _PAM_LEN, (locus, whole)

        # The PAM is 3' of the protospacer *on the strand the guide reads*, so on the
        # plus strand it is the last three bases of the window and on the minus strand
        # the reverse complement of the first three.
        pam_here = (
            whole[-_PAM_LEN:]
            if locus.strand is Strand.PLUS
            else reverse_complement(whole[:_PAM_LEN])
        )
        assert pam_here == site.pam_sequence, (locus, whole, pam_here, site.pam_sequence)


def test_the_shift_is_load_bearing(planted: tuple[ReferenceGenome, str]) -> None:
    """A minus-strand anchor must differ from the protospacer start, or the check above
    would pass with the shift removed."""
    reference, _ = planted
    report = search(_SPACER, _PAM, reference=reference)
    minus = [s for s in report.sites if s.locus.strand is Strand.MINUS]
    assert minus, "no minus-strand site; the shift is never exercised"
    loci = CasOffinderAdapter.reference_loci(report)
    for site in minus:
        assert (site.locus.chrom, site.locus.start, Strand.MINUS) not in loci, (
            "the unshifted protospacer start is being reported as the anchor"
        )
