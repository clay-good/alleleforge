"""The scan's cost is per *anchor*, and it was paying for things only *hits* need.

`_scan_one_strand` walks every PAM occurrence in a contig — half a million of them on
2 Mb, and about 180 million on hg38 — and for each one it used to:

* call `_evaluate`, whose only job is to re-answer "is the native kernel built?", a
  question with one answer for the whole scan;
* materialize `match.group(1)`, the PAM sequence, which is used only if the anchor turns
  into a hit;
* slice `seq[start:pam_at]` to ask whether the protospacer window contains an `N`.

None of the three changes a result, so none of them was visible to any test — and the
ratio of anchors to hits is the whole shape of this function: two hits out of 498,957
anchors in the measurement below.

The dispatch is made once per scan (`_anchor_evaluator`), the PAM string is read only for
an anchor that became a hit, and the `N` check is a `find` over the same span with no
copy. Paired, alternating, minimum of seven, in one process on a loaded machine — read the
ratio and not the absolutes: **1.33x** on a 2 Mb contig at the default budget, with the
hit tuples byte-identical.

This file pins the properties the change relies on, not the timing: the repo's own note
says a cross-run timing is not a baseline.
"""

from __future__ import annotations

from alleleforge.offtarget import _search
from alleleforge.types.guide import PAM

SPACER = "GACCATGCAACCTTGAACGT"
NGG = PAM(pattern="NGG")


def _seq(prefix: str, suffix: str = "") -> str:
    return prefix + SPACER + "TGG" + suffix


def test_a_hit_still_carries_the_pam_it_was_found_with() -> None:
    """The string that is now read late: it is what a site reports as its PAM."""
    hits = _search._scan_one_strand(
        SPACER, _seq("T" * 30, "T" * 30), NGG, max_mm=0, dna_bulges=0, rna_bulges=0
    )
    assert hits, "the fixture must produce a hit or this proves nothing"
    assert [h[2] for h in hits] == ["TGG"]


def test_an_n_in_the_protospacer_window_is_still_refused() -> None:
    """`find` over the span, not a slice — the same rejection, no copy."""
    masked = SPACER[:5] + "N" + SPACER[6:]
    seq = "T" * 30 + masked + "TGG" + "T" * 30
    assert _search._scan_one_strand(SPACER, seq, NGG, max_mm=4, dna_bulges=0, rna_bulges=0) == []


def test_the_evaluator_is_the_one_evaluate_would_have_chosen() -> None:
    """`_evaluate` stays as the shape the parity test compares; this must agree with it."""
    seq = _seq("T" * 30, "T" * 30)
    evaluate = _search._anchor_evaluator(SPACER, seq, 3, max_mm=4, dna_bulges=1, rna_bulges=1)
    pam_at = seq.index(SPACER) + len(SPACER)
    assert evaluate(pam_at) == _search._evaluate(
        SPACER, seq, pam_at, 3, max_mm=4, dna_bulges=1, rna_bulges=1
    )


def test_the_two_scanners_still_agree_on_a_contig_with_several_anchors() -> None:
    """Linear and FM-index enumeration must remain byte-identical after the rewrite."""
    from alleleforge.genome.index import FMIndex

    seq = ("T" * 12 + SPACER + "TGG" + "A" * 9 + "CGG" + "GACCATGCAACCTTGAACGA" + "AGG") * 3
    fm = FMIndex.build(seq, in_memory=True, prefer_native=False)
    linear = _search._scan_one_strand(SPACER, seq, NGG, max_mm=4, dna_bulges=1, rna_bulges=1)
    indexed = _search._scan_one_strand_fm(
        SPACER, seq, NGG, fm, max_mm=4, dna_bulges=1, rna_bulges=1
    )
    assert linear == indexed
    assert linear, "the fixture must produce hits or this proves nothing"
