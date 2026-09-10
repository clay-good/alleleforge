"""SpCas9 cuts in one place. This repository computed it in three, and two disagreed.

The same twenty bases with the same PAM, cut by the same enzyme, must give the same
coordinate whatever the reagent is called. Three places compute it:

* `enumerate.prime` — the pegRNA's `nick_site`;
* `enumerate.prime._select_nicking_guide` — the PE3 guide's nick, via `nick_offset`;
* `enumerate.cas9` — the nuclease guide's `cut_site`.

On the plus strand all three agreed. On the **minus** strand the pegRNA said 102 and the
other two said 103 and 163-for-162 — each having taken the base on the far side of the cut.
Neither was visible from inside its own chemistry: every test aimed at each computation
passed, because each is self-consistent. The defect is in the *relationship*, and nothing
compared them.

What the two wrong ones fed: `nick_offset` is printed as `nick-distance:+Nnt`, decides
`close-nick` (two nicks close enough to act as a staggered double-strand break, the outcome
prime editing exists to avoid) and gates the 40-90 nt optimal window; `cut_site` centres the
NHEJ outcome window the indel spectrum is predicted over, and is printed as `cut N`.

The convention, now shared: **the first base 3' of the cut along the strand that reads the
protospacer** — `end - 3` on the plus strand, `start + 2` on the minus.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent

_START, _END = 100, 120
_NGRNA_AT = (160, 180)
_TRANSITION = {"A": "G", "G": "A", "C": "T", "T": "C"}


def _contig(strand: str) -> str:
    body = ["T"] * 300
    body[_START:_END] = list("ACGTACGTACGTACGTACGT")
    if strand == "+":
        body[_END : _END + 3] = list("TGG")
        body[157:160] = list("CCA")  # a minus-strand ngRNA PAM, inside the frame
        body[_NGRNA_AT[0] : _NGRNA_AT[1]] = list("ACGTTGCAAGGCTTACCGTA")
    else:
        body[_START - 3 : _START] = list("CCA")
    return "".join(body)


def _reference(tmp_path: Path, strand: str) -> ReferenceGenome:
    fasta = tmp_path / f"{strand}.fa"
    fasta.write_text(">chr1\n" + _contig(strand) + "\n")
    return ReferenceGenome(fasta, build="hg38")


def _variant(strand: str, one_based: int) -> str:
    base = _contig(strand)[one_based - 1]
    return f"chr1:{one_based}:{base}>{_TRANSITION[base]}"


@pytest.mark.parametrize(
    ("strand", "edited", "expected"),
    [("+", 118, _END - 3), ("-", 102, _START + 2)],
)
def test_the_nuclease_and_the_pegrna_cut_at_the_same_base(
    strand: str, edited: int, expected: int, tmp_path: Path
) -> None:
    reference = _reference(tmp_path, strand)
    variant = _variant(strand, edited)
    span = f"chr1:{_START}-{_END}({strand})"

    knock_out = design(
        variant, reference=reference, run_offtarget=False, intent=EditIntent.KNOCK_OUT
    )
    nuclease = [
        c
        for c in knock_out.candidates
        if c.chemistry.value == "cas9_nuclease" and str(c.guide.placement) == span
    ]
    corrected = design(variant, reference=reference, run_offtarget=False)
    pegrnas = [
        c
        for c in corrected.candidates
        if c.chemistry.value == "prime" and str(c.pegrna.placement) == span
    ]
    assert nuclease and pegrnas, "the fixture no longer offers both reagents at this protospacer"

    assert nuclease[0].guide.cut_site == expected, nuclease[0].guide.cut_site
    assert pegrnas[0].pegrna.nick_site == expected, pegrnas[0].pegrna.nick_site


def test_the_nicking_guide_agrees_with_the_other_two(tmp_path: Path) -> None:
    """The third computation, on the strand where all three used to differ."""
    reference = _reference(tmp_path, "+")
    corrected = design(_variant("+", 118), reference=reference, run_offtarget=False)
    plus = [
        c
        for c in corrected.candidates
        if c.chemistry.value == "prime" and str(c.pegrna.placement).endswith("(+)")
    ]
    span = f"chr1:{_NGRNA_AT[0]}-{_NGRNA_AT[1]}"
    guide = next(
        c.pegrna.nicking_guide
        for c in plus
        if c.pegrna.nicking_guide is not None
        and str(c.pegrna.nicking_guide.placement).startswith(span)
    )
    # The guide reads on the minus strand: `start + 2`, the same rule the pegRNA uses.
    assert guide.nick_offset + plus[0].pegrna.nick_site == _NGRNA_AT[0] + 2


def test_the_two_strands_would_not_pass_one_formula(tmp_path: Path) -> None:
    """Both strands, because the disagreement was minus-strand only.

    A plus-strand-only check passed for the whole life of both defects.
    """
    assert _END - 3 != _START + 2
