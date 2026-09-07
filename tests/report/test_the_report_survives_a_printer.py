"""Printing the HTML report cut 340px off every cloning duplex.

Paper has no affordances. A `overflow-x: auto` box scrolls on screen and is simply cut
off by a printer, and the report had no `@media print` rules at all. Measured at a 624px
print column, with the print rules applied and then removed on the same page:

    screen rules   pre scrollWidth 876, clientWidth 536  -> 340px hidden
    print rules    pre scrollWidth 536, clientWidth 536  ->   0px hidden

340px is the tail of every `top`/`bottom` duplex. This is the third route by which this
report has handed someone a truncated sequence — after the PDF's right margin and its page
breaks — and the same order goes wrong at the end of it.

Two more things paper takes away. Browsers drop backgrounds when printing, which would
erase the panels that separate a cloning-lethal warning from a footnote; the two that
carry meaning are marked to print. And a candidate split across sheets is a reagent read
half on each.
"""

from __future__ import annotations

import re

import pytest

from alleleforge.report.builder import build_report
from alleleforge.report.html import _STYLE, render_html
from alleleforge.types.candidate import RankedMenu


def _print_block() -> str:
    match = re.search(r"@media print \{(.*?)\n\}", _STYLE, re.S)
    assert match, "the report stylesheet has no @media print block"
    return match.group(1)


def _print_rule(selector: str) -> str:
    block = _print_block()
    match = re.search(rf"(?:^|\n)\s*{re.escape(selector)}[^{{]*\{{([^}}]*)\}}", block)
    assert match, f"no `{selector}` rule inside @media print:\n{block}"
    return match.group(1).replace(" ", "")


def test_the_report_has_print_rules_at_all() -> None:
    assert _print_block().strip(), _STYLE[-400:]


def test_a_sequence_wraps_on_paper_instead_of_being_clipped() -> None:
    """On screen the box scrolls; a printer has nothing to scroll."""
    rule = _print_rule("pre")
    assert "white-space:pre-wrap" in rule, rule
    assert "overflow:visible" in rule, rule


def test_the_screen_rule_still_scrolls_rather_than_wrapping() -> None:
    """Wrapping a spacer on screen would put a copyable sequence on two lines."""
    screen = re.search(r"(?:^|\n|\}\s*)pre\s*\{([^}]*)\}", _STYLE.split("@media print")[0])
    assert screen, "the screen `pre` rule is gone"
    assert "overflow-x: auto" in screen.group(1), screen.group(1)


@pytest.mark.parametrize("selector", [".candidate", ".chart", "table"])
def test_a_block_is_not_split_across_sheets(selector: str) -> None:
    assert "break-inside:avoid" in _print_rule(".candidate"), _print_block()
    assert selector in _print_block(), _print_block()


def test_the_panels_that_carry_meaning_are_printed() -> None:
    """A hazard that prints as ordinary prose is the R310 defect, on paper."""
    rule = _print_rule(".hazard")
    assert "print-color-adjust:exact" in rule, rule
    assert ".disclaimer" in _print_block()


def test_the_rules_reach_a_rendered_report(prime_menu: RankedMenu) -> None:
    html = render_html(build_report(prime_menu, with_oligos=True))
    assert "@media print" in html
    assert "white-space: pre-wrap" in html.split("@media print")[1][:400]
