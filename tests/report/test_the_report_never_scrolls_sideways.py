"""The rationale laid out 5,903px wide in a 1,217px column and moved the whole page.

Measured in a browser on a real report:

    <pre> scrollWidth 5903, clientWidth 1217
    documentElement.scrollWidth 5927, clientWidth 1265  -> the *document* scrolls sideways

`<pre>` defaults to `white-space: pre` and has no overflow rule, and the rationale is one
long line per routing decision. So the report's explanation section — the part that says
why each chemistry declined — ran nearly five times past the right edge, and reading it
meant scrolling the document, which drags the disclaimer, the charts and every candidate
off-screen with it.

The two `<pre>` blocks want different answers and now get them. The rationale is prose and
wraps. The oligo block is DNA: a spacer broken across two lines is a spacer someone
mis-copies into an order form, so it keeps its line and scrolls inside its own box.
Neither may move the page.
"""

from __future__ import annotations

import re

import pytest

from alleleforge.report.builder import build_report
from alleleforge.report.html import _STYLE, render_html
from alleleforge.types.candidate import RankedMenu


def _rule(selector: str) -> str:
    match = re.search(rf"(?:^|\n|}}\s*){re.escape(selector)}\s*\{{([^}}]*)\}}", _STYLE)
    assert match, f"no `{selector}` rule in the report stylesheet"
    return match.group(1).replace(" ", "")


def test_every_pre_is_bounded_by_its_container() -> None:
    block = _rule("pre")
    assert "max-width:100%" in block, block
    assert "overflow-x:auto" in block, block


def test_the_rationale_wraps_rather_than_scrolling() -> None:
    """Prose in a horizontally scrolling box is prose nobody scrolls."""
    block = _rule(".rationale-block")
    assert "white-space:pre-wrap" in block, block
    assert "overflow-wrap:anywhere" in block, block


def test_the_rationale_block_is_the_one_that_carries_it(prime_menu: RankedMenu) -> None:
    html = render_html(build_report(prime_menu))
    rationale = re.search(r"<pre class='([^']*)'>([^<]*Routing:[^<]*)</pre>", html, re.S)
    assert rationale, "the rationale is no longer rendered in a <pre>"
    assert "rationale-block" in rationale.group(1), rationale.group(1)


def test_the_oligo_block_keeps_its_lines(prime_menu: RankedMenu) -> None:
    """A wrapped spacer is a spacer someone mis-copies into a vendor form."""
    html = render_html(build_report(prime_menu, with_oligos=True))
    oligo = re.search(r"<pre class='([^']*)'>[^<]*cloning oligos", html)
    assert oligo, "the oligo block is no longer rendered in a <pre>"
    assert "rationale-block" not in oligo.group(1), oligo.group(1)


@pytest.mark.parametrize("selector", ["pre", ".rationale-block", "table"])
def test_wide_content_declares_how_it_handles_being_wide(selector: str) -> None:
    """Every element that can exceed the column says what it does about it."""
    if selector == "table":
        # A table's own overflow is the browser's; what matters is that nothing here
        # sets a fixed width that could exceed the column.
        assert "width:" not in _rule(selector), _rule(selector)
        return
    block = _rule(selector)
    assert "overflow" in block or "white-space" in block, block
