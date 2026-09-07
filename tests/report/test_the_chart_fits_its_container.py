"""The responsive rule was written for the wrapper and never reached the picture.

    .chart { width:100%; max-width:760px; height:320px; }

`width:100%` says the intent plainly. But the chart is an *inlined* SVG carrying its own
`width="720" height="380"`, and those win. Measured in a browser:

    box 320px tall around a 380px drawing   -> 60px of chart painted over the heading below
    375px viewport, svg 720px               -> document 744px wide: the page scrolls sideways

The SVG has a `viewBox` and could have scaled the whole time. Styling the element rather
than the box, and taking the aspect ratio from the viewBox, gives 760x401 on a desktop and
327x173 at 375px with no sideways scroll — both measured, before and after, on the same
page.

The rules here are what a stylesheet can be checked for; the numbers above are what a
browser had to be asked.
"""

from __future__ import annotations

import re

import pytest

from alleleforge.report.html import _STYLE


def _rule(selector: str) -> str:
    match = re.search(rf"(?:^|\n|}}\s*){re.escape(selector)}\s*\{{([^}}]*)\}}", _STYLE)
    assert match, f"no `{selector}` rule in the report stylesheet"
    return match.group(1).replace(" ", "")


def test_the_svg_itself_is_styled_not_only_its_box() -> None:
    """An inlined SVG's own width/height attributes beat any rule on its wrapper."""
    svg_rule = _rule(".chart svg")
    assert "width:100%" in svg_rule, svg_rule
    assert "height:auto" in svg_rule, svg_rule


def test_the_box_does_not_impose_a_height_the_drawing_ignores() -> None:
    """A fixed box height around a taller drawing is 60px of chart over the next heading."""
    box = _rule(".chart")
    assert "height:" not in box, box
    assert "width:100%" in box and "max-width" in box, box


def test_the_drawing_carries_the_viewbox_that_makes_scaling_possible() -> None:
    from alleleforge.viz.svg import Series, bar_chart

    svg = bar_chart(
        title="t",
        categories=("a", "b"),
        series=(Series(name="s", values=(0.5, 0.6), color="#0a7d77"),),
    )
    assert 'viewBox="0 0 720 380"' in svg, svg[:200]


@pytest.mark.parametrize("selector", [".chart", ".chart svg"])
def test_nothing_here_sets_a_pixel_width(selector: str) -> None:
    """A fixed width is what defeated the responsive intent the first time."""
    rule = _rule(selector)
    assert not re.search(r"(?<!max-)width:\d+px", rule), rule
