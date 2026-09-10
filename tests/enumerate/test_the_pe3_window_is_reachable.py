"""The optimal PE3 window was documented at 40-90 nt and only 40-57 could be reached.

`DEFAULT_PE3_OFFSET = (40, 90)` is the range this project tells a user to prefer a nicking
guide from. The enumeration frame is `edit +/- margin`, and the margin was sized for what a
*pegRNA* needs — a protospacer, its PAM, the longest RTT and PBS, the allele. A nicking
guide's protospacer has to fit inside that same frame to be seen at all, and with 75 bases
of it the largest nick-to-nick offset the enumerator could ever return was **57**.

Not rejected: never looked at. A guide 70 nt away is inside the documented optimal window,
is a better PE3 partner than one at 41, and no run could offer it. The bias ran the wrong
way, too — the reachable half is the half closer to `close-nick`, the staggered
double-strand break prime editing is chosen to avoid.

This walks a nicking guide out from the edit and requires the offsets the enumerator
actually returns to cover the window it documents. The failure it catches is silence, so the
check has to be a sweep: any single distance inside 40-57 passed before the fix.
"""

from __future__ import annotations

from pathlib import Path

from alleleforge.design.designer import design
from alleleforge.enumerate.prime import DEFAULT_PE3_OFFSET
from alleleforge.genome.reference import ReferenceGenome

_PEG_AT = (100, 120)
_NGRNA = "ACGTTGCAAGGCTTACCGTA"


def _offsets_for(tmp_path: Path, ngrna_lo: int) -> set[int]:
    """Design with a minus-strand nicking-guide protospacer starting at ``ngrna_lo``."""
    body = ["T"] * 400
    body[_PEG_AT[0] : _PEG_AT[1]] = list("ACGTACGTACGTACGTACGT")
    body[_PEG_AT[1] : _PEG_AT[1] + 3] = list("TGG")
    body[ngrna_lo - 3 : ngrna_lo] = list("CCA")
    body[ngrna_lo : ngrna_lo + 20] = list(_NGRNA)
    fasta = tmp_path / f"{ngrna_lo}.fa"
    fasta.write_text(">chr1\n" + "".join(body) + "\n")
    menu = design(
        "chr1:118:C>T",
        reference=ReferenceGenome(fasta, build="hg38"),
        run_offtarget=False,
    )
    return {
        c.pegrna.nicking_guide.nick_offset
        for c in menu.candidates
        if c.chemistry.value == "prime"
        and str(c.pegrna.placement).endswith("(+)")
        and c.pegrna.nicking_guide is not None
    }


def test_the_whole_documented_window_is_reachable(tmp_path: Path) -> None:
    low, high = DEFAULT_PE3_OFFSET
    reachable: set[int] = set()
    for ngrna_lo in range(130, 220, 2):
        reachable |= _offsets_for(tmp_path, ngrna_lo)
    inside = {offset for offset in reachable if low <= offset <= high}
    assert inside, "no PE3 guide was found at any distance"
    assert max(inside) >= high - 1, (
        f"the largest reachable nick-to-nick offset is {max(inside)}, and "
        f"`DEFAULT_PE3_OFFSET` documents the optimal window as {DEFAULT_PE3_OFFSET}. "
        "A guide beyond the enumeration frame is not rejected, it is never looked at."
    )
    assert min(inside) <= low + 1, min(inside)


def test_a_guide_beyond_the_window_is_still_refused(tmp_path: Path) -> None:
    """Widening the frame must not widen the *window*: past 90 is still not offered."""
    _low, high = DEFAULT_PE3_OFFSET
    beyond = set()
    for ngrna_lo in range(220, 260, 2):
        beyond |= _offsets_for(tmp_path, ngrna_lo)
    assert not [offset for offset in beyond if offset > high], sorted(beyond)


def test_the_frame_still_costs_what_the_pegrna_needs(tmp_path: Path) -> None:
    """The margin is a max, not a sum: a run with no PE3 search pays nothing for it."""
    import inspect

    from alleleforge.enumerate import prime

    source = inspect.getsource(prime.enumerate_prime)
    assert "max(pegrna_reach, pe3_reach)" in source
    assert "if pe3 else 0" in source
