"""A 180-nt donor split across two pages of the sheet it is copied from.

Pages were a blind fixed-size chunk:

    pages = [lines[i : i + _LINES_PER_PAGE] for i in range(0, len(lines), _LINES_PER_PAGE)]

A long HDR donor wraps to three lines, and with the right amount of content above it those
land at 46, 47 and 48 — two at the foot of one page and one at the head of the next. The
person copying that donor into a vendor form has to notice it continues overleaf, and the
failure when they do not is a truncated reagent: the same consequence the measured line
wrapping was introduced to prevent, arriving by a different route.

A run of sequence lines that would straddle a break is moved whole to the next page. The
properties that matter are checked across every offset that can produce the collision,
not on one lucky fixture: no line is lost, no page is over-long, and no run is divided.
"""

from __future__ import annotations

import re

import pytest

from alleleforge.report.oligos import LENTIGUIDE_BSMBI, donor_oligo, sgrna_oligos
from alleleforge.report.pdf import _LINES_PER_PAGE, _SEQUENCE_LINE, _paginate, oligo_lines
from alleleforge.types.guide import HDRDonor
from alleleforge.types.sequence import DNASequence


def _donor_block(nt: int = 180) -> list[str]:
    sequence = ("ACGT" * (nt // 4 + 1))[:nt]
    donor = donor_oligo(HDRDonor(sequence=DNASequence(sequence=sequence), recut_blocked=True))
    guide = sgrna_oligos("ACGTACGTACGTACGTACGT", scheme=LENTIGUIDE_BSMBI, kind="sgrna")
    return oligo_lines(guide.model_copy(update={"donor": donor}))


def _page_of(pages: list[list[str]]) -> list[int]:
    return [index for index, page in enumerate(pages) for _ in page]


def test_the_fixture_wraps_to_several_sequence_lines() -> None:
    """Without a multi-line sequence there is nothing here to split."""
    run = [line for line in _donor_block() if _SEQUENCE_LINE.match(line)]
    assert len(run) >= 3, run


@pytest.mark.parametrize("pad", range(0, 60))
def test_no_sequence_run_is_divided(pad: int) -> None:
    lines = ["filler"] * pad + _donor_block()
    pages = _paginate(lines)
    page_of = _page_of(pages)
    run = [i for i, line in enumerate(lines) if _SEQUENCE_LINE.match(line)]
    assert len({page_of[i] for i in run}) == 1, (pad, run, [page_of[i] for i in run])


@pytest.mark.parametrize("pad", range(0, 60))
def test_pagination_loses_nothing_and_overfills_nothing(pad: int) -> None:
    lines = ["filler"] * pad + _donor_block()
    pages = _paginate(lines)
    assert [line for page in pages for line in page] == lines, pad
    assert all(len(page) <= _LINES_PER_PAGE for page in pages), pad


def test_a_run_longer_than_a_page_is_still_emitted() -> None:
    """Unavoidable: breaking it somewhere is required, and looping instead is not a fix."""
    lines = ["A" * 40] * (_LINES_PER_PAGE * 2 + 5)
    pages = _paginate(lines)
    assert [line for page in pages for line in page] == lines
    assert all(len(page) <= _LINES_PER_PAGE for page in pages)


def test_prose_still_flows_across_the_break() -> None:
    """Only sequences are kept together; holding back prose would waste whole pages."""
    lines = [f"line {i}" for i in range(_LINES_PER_PAGE + 10)]
    pages = _paginate(lines)
    assert len(pages[0]) == _LINES_PER_PAGE, len(pages[0])


def test_the_pattern_matches_a_sequence_and_not_prose() -> None:
    assert _SEQUENCE_LINE.match("      ACGTACGTACGTACGTACGT")
    assert _SEQUENCE_LINE.match("      5'-ACGTACGTACGTACGT-3'")
    assert not _SEQUENCE_LINE.match("      note: a 5' G was prepended for U6 transcription")
    assert not _SEQUENCE_LINE.match("  cloning oligos (px330-bbsi, BbsI):")
    # A spacer inside a reagent line is prose around a sequence, not a sequence line.
    assert not _SEQUENCE_LINE.match("    SpCas9 sgRNA ACGTACGTACGTACGTACGT (NGG PAM)")
    assert not re.match(r"^\s*$", "x")
