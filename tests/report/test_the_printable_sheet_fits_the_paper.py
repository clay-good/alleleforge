"""A 180-nt donor ran 110pt off the right edge of the page it is printed on.

The PDF wrapped at a fixed *character* count — `_WRAP = 92`, "characters per line at 10pt
Helvetica within the margins". Helvetica is proportional, so 92 characters is 460pt of
lowercase prose and 614pt of upper-case DNA, on a 504pt column:

    ACGTACGTACGT…  614.0pt  (+110)

An HDR donor is a single unbroken token of A, C, G and T — the widest glyphs in the face —
and it is the sequence a bench scientist copies into a vendor form off the printed sheet.
It was truncated at the paper's edge. The `=` rule under the title overflowed too, by 33pt,
on the first page of every report ever produced.

Wrapping is measured now, against real Adobe Helvetica advance widths. A token wider than
the column is broken at the last character that fits, because a wrapped sequence is
recoverable and a truncated one is not — and the guards check that it reassembles.
"""

from __future__ import annotations

import pytest

from alleleforge.report.builder import build_report
from alleleforge.report.oligos import LENTIGUIDE_BSMBI, donor_oligo, sgrna_oligos
from alleleforge.report.pdf import _TEXT_W, _rule, _text_width, _wrap, oligo_lines, render_pdf
from alleleforge.types.candidate import RankedMenu
from alleleforge.types.guide import HDRDonor
from alleleforge.types.sequence import DNASequence
from tests.pdf_text import pdf_runs


def _donor_block(nt: int) -> list[str]:
    sequence = ("ACGT" * (nt // 4 + 1))[:nt]
    donor = donor_oligo(HDRDonor(sequence=DNASequence(sequence=sequence), recut_blocked=True))
    guide = sgrna_oligos("ACGTACGTACGTACGTACGT", scheme=LENTIGUIDE_BSMBI, kind="sgrna")
    return oligo_lines(guide.model_copy(update={"donor": donor})), sequence


@pytest.mark.parametrize("nt", [60, 120, 180, 240])
def test_no_line_runs_off_the_page(nt: int) -> None:
    lines, _ = _donor_block(nt)
    over = [
        (round(_text_width(line), 1), line[:40]) for line in lines if _text_width(line) > _TEXT_W
    ]
    assert not over, (nt, _TEXT_W, over)


@pytest.mark.parametrize("nt", [60, 120, 180, 240])
def test_a_wrapped_donor_reassembles_exactly(nt: int) -> None:
    """A wrapped sequence is recoverable; a truncated one is a mis-ordered reagent."""
    lines, sequence = _donor_block(nt)
    start = next(i for i, line in enumerate(lines) if line.strip().startswith("5'-"))
    end = next(i for i, line in enumerate(lines[start:], start) if line.strip().endswith("-3'"))
    joined = "".join(line.strip() for line in lines[start : end + 1])
    assert joined.removeprefix("5'-").removesuffix("-3'") == sequence, (nt, joined[:60])


def test_the_two_oligo_labels_stay_in_one_column() -> None:
    """`top    5'-` is padded to align with `bottom 5'-`; wrapping must not eat it."""
    lines, _ = _donor_block(60)
    top = next(line for line in lines if line.strip().startswith("top"))
    bottom = next(line for line in lines if line.strip().startswith("bottom"))
    assert top.index("5'-") == bottom.index("5'-"), (top, bottom)


@pytest.mark.parametrize("char", ["=", "-"])
def test_a_rule_fills_the_column_without_exceeding_it(char: str) -> None:
    rule = _rule(char)
    assert rule, char
    assert _text_width(rule) <= _TEXT_W, (char, _text_width(rule))
    assert _text_width(rule + char) > _TEXT_W, "the rule stops short of the column"


def test_wrapping_measures_rather_than_counts() -> None:
    """The two strings have the same length and very different widths."""
    narrow, wide = "i" * 90, "M" * 90
    assert len(_wrap(narrow)) < len(_wrap(wide)), (len(_wrap(narrow)), len(_wrap(wide)))
    for line in _wrap(wide):
        assert _text_width(line) <= _TEXT_W


def test_the_whole_document_fits(prime_menu: RankedMenu) -> None:
    """End to end, on every text run the writer actually emits."""
    runs = pdf_runs(render_pdf(build_report(prime_menu, with_oligos=True)))
    assert runs, "no text runs in the PDF"
    over = [(round(_text_width(r), 1), r[:40]) for r in runs if _text_width(r) > _TEXT_W]
    assert not over, over
