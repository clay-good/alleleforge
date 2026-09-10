"""The reagent, applied as designed, produces the intended allele — on both strands.

`test_rtt_encodes_the_edit` checks that the desired base sits at the right offset inside
the RTT, on the plus strand. Two things it cannot see. It reads one base, so a template
correct at the edit and wrong in its homology arms passes — and homology is what makes the
flap anneal. And it is plus-strand only, so the minus-strand arithmetic (a reverse
complement, and a window that runs *downward* from the nick) is an assumption.

This writes the template into the sequence the way the mechanism does and compares the
whole result. For `intent=correct` the answer is exact: the corrected allele is the
reference, so writing the RTT at the nick must reproduce the reference across the RTT's
whole span, homology arms included.

The two strands index `nick_site` differently — it is the first base downstream of the cut
*along the protospacer's own strand* — which is the asymmetry a plus-strand-only test lets
you never notice, and is now written down on the field itself.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.sequence import DNASequence

_START, _END = 100, 120
_TRANSITION = {"A": "G", "G": "A", "C": "T", "T": "C"}


#: A protospacer for the PE3 nicking guide, on the strand the pegRNA does not cut and
#: 40-90 nt from its nick. Placed *inside* the enumeration frame, which is
#: `edit +/- (spacer + PAM + max RTT + max PBS + allele)` = 75 bases here: a guide beyond
#: it is never considered, which is what the first version of this fixture got wrong and
#: what made "no PE3 candidate" look like a defect. Non-repetitive, because a poly-T
#: stretch is filtered as a Pol III terminator before it can be a guide.
_NGRNA_SEQ = "ACGTTGCAAGGCTTACCGTA"


def _contig(strand: str) -> str:
    body = ["T"] * 300
    body[_START:_END] = list("ACGTACGTACGTACGTACGT")
    if strand == "+":
        body[_END : _END + 3] = list("TGG")
        # The nicking guide reads on the minus strand, so its PAM is `CCN` on the plus
        # strand immediately 5' of its protospacer.
        body[157:160] = list("CCA")
        body[160:180] = list(_NGRNA_SEQ)
    else:
        body[_START - 3 : _START] = list("CCA")
        # ...and on the plus strand for a minus-strand pegRNA, with `NGG` 3' of it.
        body[35:55] = list(_NGRNA_SEQ)
        body[55:58] = list("TGG")
    return "".join(body)


def _pegrnas(tmp_path: Path, strand: str, edited: int) -> tuple[str, list]:
    sequence = _contig(strand)
    fasta = tmp_path / f"{strand}.fa"
    fasta.write_text(">chr1\n" + sequence + "\n")
    base = sequence[edited - 1]
    menu = design(
        f"chr1:{edited}:{base}>{_TRANSITION[base]}",
        reference=ReferenceGenome(fasta, build="hg38"),
        run_offtarget=False,
    )
    return sequence, [
        candidate.pegrna
        for candidate in menu.candidates
        if candidate.chemistry.value == "prime"
        and str(candidate.pegrna.placement).endswith(f"({strand})")
    ]


def _written_window(pegrna: object, strand: str) -> tuple[int, int, str]:
    """Return the plus-strand span the RTT writes, and what it writes there.

    The RTT is synthesized along the protospacer's own strand from the new 3' end, so on
    the plus strand it runs up from `nick_site` and on the minus strand down from it.
    """
    rtt = str(pegrna.rtt)  # type: ignore[attr-defined]
    nick = pegrna.nick_site  # type: ignore[attr-defined]
    if strand == "+":
        return nick, nick + len(rtt), str(DNASequence(rtt).reverse_complement())
    return nick - len(rtt) + 1, nick + 1, rtt


@pytest.mark.parametrize(("strand", "edited"), [("+", 118), ("-", 102)])
def test_the_template_reproduces_the_reference_across_its_whole_span(
    strand: str, edited: int, tmp_path: Path
) -> None:
    sequence, pegrnas = _pegrnas(tmp_path, strand, edited)
    assert pegrnas, f"no {strand}-strand pegRNA to check"
    for pegrna in pegrnas:
        start, end, written = _written_window(pegrna, strand)
        assert sequence[start:end] == written, (
            f"{strand} strand: the RTT writes {written!r} into [{start},{end}), where the "
            f"reference has {sequence[start:end]!r}. Correcting installs the reference, so "
            "these must agree across the whole template, homology arms included."
        )


@pytest.mark.parametrize(("strand", "edited"), [("+", 118), ("-", 102)])
def test_the_template_spans_the_edited_base(strand: str, edited: int, tmp_path: Path) -> None:
    """A template that agrees with the reference and does not reach the edit corrects
    nothing — and would pass the check above."""
    _sequence, pegrnas = _pegrnas(tmp_path, strand, edited)
    for pegrna in pegrnas:
        start, end, _written = _written_window(pegrna, strand)
        assert start <= edited - 1 < end, (
            f"{strand} strand: the RTT writes [{start},{end}), which does not cover the "
            f"edited base at {edited - 1}"
        )


def test_the_two_strands_write_different_windows(tmp_path: Path) -> None:
    """The asymmetry a plus-strand-only test lets you never notice.

    `nick_site` is the first base downstream of the cut *along the protospacer's strand*,
    so the plus-strand span runs up from it and the minus-strand span runs down. Applying
    one rule to both reconstructs the wrong window on one of them.
    """
    _plus_seq, plus = _pegrnas(tmp_path, "+", 118)
    _minus_seq, minus = _pegrnas(tmp_path, "-", 102)
    plus_start, plus_end, _ = _written_window(plus[0], "+")
    minus_start, minus_end, _ = _written_window(minus[0], "-")
    assert plus_start >= plus[0].nick_site
    assert minus_end <= minus[0].nick_site + 1
    assert (plus_start, plus_end) != (minus_start, minus_end)


@pytest.mark.parametrize(("strand", "edited"), [("+", 118), ("-", 102)])
def test_the_nicking_guides_offset_is_its_own_geometry(
    strand: str, edited: int, tmp_path: Path
) -> None:
    """The third piece of nick arithmetic, and the one two mutations walked past.

    A PE3 candidate has two nicks. `nick_offset` is the distance between them, and it is
    what `close-nick` is computed from — the caveat that says the pair may act as a
    staggered double-strand break, the outcome prime editing exists to avoid. It is stored
    as a number, so a wrong one is invisible: the flag simply appears or does not.

    Recomputed here from the nicking guide's own placement by the same two strand
    formulas the pegRNA's nick uses, and required to agree. An independent recomputation
    is the only check available when the quantity is a stored scalar.
    """
    _sequence, pegrnas = _pegrnas(tmp_path, strand, edited)
    with_ngrna = [p for p in pegrnas if p.nicking_guide is not None]
    assert with_ngrna, f"no {strand}-strand PE3 candidate to measure"
    for pegrna in with_ngrna:
        guide = pegrna.nicking_guide
        span = guide.placement
        # Three bases 5' of the PAM, counted along the guide's own strand.
        expected_nick = span.end - 3 if span.strand.value == "+" else span.start + 2
        # The guide's own nick, under the same convention as the pegRNA's: the first
        # base 3' of the cut along the strand that reads the protospacer.
        assert guide.nick_offset == expected_nick - pegrna.nick_site, (
            f"{strand} strand: nick_offset is {guide.nick_offset}, and the guide's "
            f"placement {span} puts its nick at {expected_nick}, which is "
            f"{expected_nick - pegrna.nick_site} from the pegRNA's at {pegrna.nick_site}"
        )


def test_a_nicking_guide_nicks_the_other_strand(tmp_path: Path) -> None:
    """PE3's whole mechanism: the second nick is on the strand the first one did not cut.

    Two nicks on the same strand are not a PE3 design at all, and nothing else in the
    candidate would say so — the offset would still be a plausible number.
    """
    for strand, edited in (("+", 118), ("-", 102)):
        _sequence, pegrnas = _pegrnas(tmp_path, strand, edited)
        for pegrna in (p for p in pegrnas if p.nicking_guide is not None):
            assert pegrna.nicking_guide.placement.strand is not pegrna.placement.strand, (
                f"{strand} strand: the nicking guide is on the same strand as the pegRNA"
            )


def test_one_protospacer_nicks_at_one_base_whichever_role_it_plays(tmp_path: Path) -> None:
    """The check that found the defect this file's fixture now pins.

    A protospacer is a protospacer: the same twenty bases with the same PAM, cut by the
    same enzyme, must nick at the same coordinate whether they are enumerated as a
    pegRNA or selected as its nicking guide. They did not — the two computations used
    different conventions for which side of the cut to index, so one contig gave 162 as a
    pegRNA and 163 as a nicking guide, and `nick_offset` (a difference of the two) was
    wrong by one in opposite directions on the two strands.

    That number is the PE3 design parameter the literature says to choose a nicking guide
    by; it also decides the `close-nick` caveat and admission to the optimal offset
    window. A one-base error in it is invisible in every other field.
    """
    sequence = _contig("+")
    fasta = tmp_path / "roles.fa"
    fasta.write_text(">chr1\n" + sequence + "\n")
    reference = ReferenceGenome(fasta, build="hg38")
    ngrna_span = "chr1:160-180"

    # As the nicking guide of the plus-strand pegRNA at [100, 120).
    plus = [
        c
        for c in design("chr1:118:C>T", reference=reference, run_offtarget=False).candidates
        if c.chemistry.value == "prime" and str(c.pegrna.placement).endswith("(+)")
    ]
    guide = next(
        c.pegrna.nicking_guide
        for c in plus
        if c.pegrna.nicking_guide is not None
        and str(c.pegrna.nicking_guide.placement).startswith(ngrna_span)
    )
    as_guide = guide.nick_offset + plus[0].pegrna.nick_site

    # ...and as a pegRNA in its own right, correcting a base within its own reach.
    base = sequence[161]
    own = [
        c
        for c in design(
            f"chr1:162:{base}>{_TRANSITION[base]}", reference=reference, run_offtarget=False
        ).candidates
        if c.chemistry.value == "prime" and str(c.pegrna.placement) == f"{ngrna_span}(-)"
    ]
    assert own, "the protospacer no longer enumerates as a pegRNA, so the roles cannot be compared"
    assert as_guide == own[0].pegrna.nick_site, (
        f"{ngrna_span} nicks at {as_guide} as a nicking guide and at "
        f"{own[0].pegrna.nick_site} as a pegRNA"
    )
