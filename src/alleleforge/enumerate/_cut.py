"""Where SpCas9 cuts, computed once.

Four call sites used to do this arithmetic by hand — the pegRNA's nick, the PE3 nicking
guide's nick, and the nuclease guide's cut site on each strand — and two of them took the
base on the *far* side of the cut for a guide reading against the frame. The same
protospacer then reported a different coordinate depending on which reagent it became:
`chr1:100-120(-)` nicked at 102 as a pegRNA and cut at 103 as a nuclease guide, and a PE3
guide's `nick_offset` (a difference of two such coordinates) was wrong by one in opposite
directions on the two strands.

Each of those functions was self-consistent and passed every test aimed at it. The defect
lived only in the relationship between them, which is what a shared rule removes: there is
no relationship left to be wrong.

**The convention.** SpCas9 cuts ``cut_offset`` bases 5' of the PAM, and the coordinate
reported is the **first base 3' of the cut along the strand that reads the protospacer** —
the base the new 3' end starts from, which is what a pegRNA's PBS anneals to and what an
RTT is written from. For a protospacer at ``[lo, hi)`` in a frame:

* reading *with* the frame (PAM at ``[hi, hi + pam)``): ``hi - cut_offset``
* reading *against* it (PAM at ``[lo - pam, lo)``): ``lo + cut_offset - 1``

They are not each other's mirror image by accident: the two expressions differ by one
because a half-open interval names its low bound and excludes its high one.
"""

from __future__ import annotations

__all__ = ["cut_index"]


def cut_index(lo: int, hi: int, *, reads_with_frame: bool, cut_offset: int) -> int:
    """Return the cut coordinate for a protospacer at ``[lo, hi)`` in frame coordinates.

    Args:
        lo: Frame index of the protospacer's low bound.
        hi: Frame index of its high bound, exclusive.
        reads_with_frame: Whether the protospacer reads 5'->3' in the frame's direction,
            which is the same as asking whether its PAM sits at the high end.
        cut_offset: Bases 5' of the PAM that the enzyme cuts (3 for SpCas9).

    Returns:
        The first base 3' of the cut along the protospacer's own strand.
    """
    return hi - cut_offset if reads_with_frame else lo + cut_offset - 1
