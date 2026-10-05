"""The PDF's layout and conditional lines, tested on their edges rather than past them.

A mutation sweep of `report/pdf.py` left 17 of 86 mutants alive. Two are equivalent:
`int(x / y)` and `x // y` agree for the positive values at L40 and L169. The other 15 were
real and shared one cause: every fixture sat comfortably inside a threshold. No test
put a token exactly one column wide, filled a page exactly, or rendered a candidate with
every allele shown. Nothing checked where on the paper the text starts. And the one test
of the cross-reference table read the row count from the table it was checking.

The exact-width strings are found from the Helvetica advance table: `"!" * 50 + "c" * 73`
and `"c" * 73 + " " + "!" * 49` both measure 504.0pt, the text column, to the bit.
"""

from __future__ import annotations

import re

from alleleforge.report.builder import build_report
from alleleforge.report.pdf import (
    _TEXT_W,
    _candidate_lines,
    _paginate,
    _text_width,
    _wrap,
    render_pdf,
)
from alleleforge.types.candidate import RankedMenu
from tests.pdf_text import pdf_text

#: US Letter, and the half-inch-and-a-quarter margin this renderer promises, as literals:
#: the module's own constants are what is under test.
_PAPER_H = 792
_MARGIN = 54
_LEADING = 14

_EXACT_TOKEN = "!" * 50 + "c" * 73
_EXACT_LINE = "c" * 73 + " " + "!" * 49


def test_the_exact_width_fixtures_are_exact() -> None:
    assert _text_width(_EXACT_TOKEN) == _TEXT_W
    assert _text_width(_EXACT_LINE) == _TEXT_W


def test_a_token_exactly_the_column_wide_is_not_broken() -> None:
    assert _wrap(_EXACT_TOKEN) == [_EXACT_TOKEN]


def test_a_word_after_an_exact_width_token_starts_its_own_line_cleanly() -> None:
    # Sending the exact-width token through the breaking path instead emits it intact
    # but leaves the next line starting with a stray space.
    assert _wrap(_EXACT_TOKEN + " ab") == [_EXACT_TOKEN, "ab"]


def test_a_token_one_glyph_too_wide_breaks_at_the_last_glyph_that_fits() -> None:
    assert _wrap(_EXACT_TOKEN + "c") == [_EXACT_TOKEN, "c"]


def test_two_words_exactly_the_column_wide_share_a_line() -> None:
    assert _wrap(_EXACT_LINE) == [_EXACT_LINE]


def test_a_glyph_wider_than_a_tiny_column_is_still_emitted_one_per_line() -> None:
    # An indent of 500.4pt leaves 3.6pt; "A" is 6.67pt. Breaking must still progress one
    # glyph at a time rather than cut to nothing and loop.
    indent = "!" * 180
    assert _wrap("AA", indent=indent) == [indent + "A", indent + "A"]


def test_an_empty_line_survives_wrapping() -> None:
    # The report's blank spacer lines are `_wrap("")`; dropping them runs sections together.
    assert _wrap("") == [""]


def test_content_that_exactly_fills_a_page_makes_one_page() -> None:
    assert _paginate(["x"] * 48) == [["x"] * 48]
    assert _paginate([]) == [[]]


def test_a_sequence_run_exactly_one_page_long_moves_whole() -> None:
    seq = "ACGT" * 5
    pages = _paginate(["prose"] + [seq] * 48)
    assert pages == [["prose"], [seq] * 48]


def test_every_line_of_a_full_page_lands_inside_the_margins(prime_menu: RankedMenu) -> None:
    pdf = render_pdf(build_report(prime_menu))
    starts = [int(y) for y in re.findall(rb"Tf \d+ (\d+) Td", pdf)]
    assert starts and all(y <= _PAPER_H - _MARGIN for y in starts)
    # The longest page `_paginate` will build must end above the bottom margin.
    longest = max(len(p) for p in _paginate(["x"] * 500))
    assert max(starts) - (longest - 1) * _LEADING >= _MARGIN


def test_the_cross_reference_table_counts_every_object(prime_menu: RankedMenu) -> None:
    pdf = render_pdf(build_report(prime_menu))
    objects = len(re.findall(rb"(?m)^\d+ 0 obj$", pdf))
    xref = pdf[int(pdf.rsplit(b"startxref", 1)[1].split(b"%%EOF")[0]) :]
    assert int(xref.split(b"\n")[1].split()[1]) == objects + 1  # plus the free entry 0
    assert f"/Size {objects + 1} ".encode() in pdf


def test_the_header_states_the_variant_and_intent_it_was_given(prime_menu: RankedMenu) -> None:
    text = pdf_text(render_pdf(build_report(prime_menu, variant="chr2:70:A>C", intent="install")))
    assert "Variant: chr2:70:A>C" in text and "(unspecified)" not in text
    assert "Intent: install" in text and "(default)" not in text
    # The builder infers an intent from the menu, so the unset case is set explicitly.
    bare = build_report(prime_menu).model_copy(update={"intent": None})
    bare_text = pdf_text(render_pdf(bare))
    assert "Variant: (unspecified)" in bare_text and "Intent: (default)" in bare_text


def test_the_withheld_alleles_note_needs_an_allele_withheld(prime_menu: RankedMenu) -> None:
    c = next(c for c in build_report(prime_menu).candidates if c.outcome_top)
    shown = len(c.outcome_top)
    all_shown = "\n".join(_candidate_lines(c.model_copy(update={"n_outcome_alleles": shown})))
    one_held = "\n".join(_candidate_lines(c.model_copy(update={"n_outcome_alleles": shown + 1})))
    assert "predicted alleles" not in all_shown
    assert f"showing {shown} of {shown + 1} predicted alleles" in one_held


def test_the_scoring_basis_is_named_only_for_a_measured_search(prime_menu: RankedMenu) -> None:
    c = build_report(prime_menu).candidates[0]

    def lines(**update: object) -> str:
        return "\n".join(_candidate_lines(c.model_copy(update=update)))

    unmeasured = {"n_offtarget_sites": None, "offtarget_scorer": "cfd"}
    assert "scoring basis" not in lines(**unmeasured, offtarget_matrix=None)
    assert "scoring basis: cfd" in lines(
        n_offtarget_sites=3, offtarget_scorer="cfd", offtarget_matrix=None
    )
    assert "scoring basis: doench" in lines(
        n_offtarget_sites=3, offtarget_scorer=None, offtarget_matrix="doench"
    )
