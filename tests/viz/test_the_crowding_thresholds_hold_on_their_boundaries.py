"""The chart's crowding thresholds, tested on their boundaries rather than past them.

Rotation, value labels, label thinning, and the crowding caption all exist because a
90-candidate prime menu printed its labels on top of one another (see
``test_a_chart_stays_inside_its_own_box``). Those tests sit comfortably past every
threshold, so a mutation sweep left the thresholds themselves free to move: ``>`` could
become ``>=``, ``max`` could become ``min``, and the suite stayed green. Each test here
puts a chart exactly on one edge, using a width chosen so the group slot is an exact
float, and asserts the side of the edge it lands on.

The group slot is ``(width - 94) / n_categories``; the label width is ``6.5px`` per char.
"""

from __future__ import annotations

import pytest

from alleleforge.viz.svg import (
    _MIN_SLOT_FOR_VALUE_LABEL,
    ReferenceLine,
    Series,
    _ordinal,
    bar_chart,
)

_VALUE_LABEL = 'font-size="11" font-weight="600"'


def _chart(categories: tuple[str, ...], width: int, **kwargs: object) -> str:
    values = tuple(0.5 for _ in categories)
    return bar_chart(
        title="T",
        categories=categories,
        series=(Series("s", values, "#000"),),
        width=width,
        **kwargs,  # type: ignore[arg-type]
    )


def test_a_label_exactly_its_slot_wide_stays_upright() -> None:
    # One category in a 65px slot: a 10-char label is 65px and fits; 11 chars overruns.
    assert "rotate(-22" not in _chart(("abcdefghij",), width=94 + 65)
    assert "rotate(-22" in _chart(("abcdefghijk",), width=94 + 65)


def test_value_labels_print_at_exactly_the_minimum_slot() -> None:
    assert _MIN_SLOT_FOR_VALUE_LABEL == 26.0  # the widths below are derived from it
    # 24 one-letter bars: wide enough that the caption fits on one line.
    cats = tuple("abcdefghijklmnopqrstuvwx")
    at_edge = _chart(cats, width=94 + 24 * 26)  # slot 26.0
    below = _chart(cats, width=94 + 24 * 26 - 1)  # slot 25.96
    assert at_edge.count(_VALUE_LABEL) == 24
    assert "bars are drawn" not in at_edge
    assert below.count(_VALUE_LABEL) == 0
    # Withholding the values is stated, not silent.
    assert "all 24 bars are drawn; too narrow to print each value" in below


def test_a_single_bar_too_narrow_for_its_value_gets_no_crowding_caption() -> None:
    # Nothing is crowding a lone bar; "all 1 bars are drawn" would be noise, and wrong.
    svg = _chart(("a",), width=94 + 16)
    assert svg.count(_VALUE_LABEL) == 0
    # A lone bar's plot is under 26px, so any caption wraps one word per line: a phrase
    # match would pass even with the caption present. Match a single word.
    assert "narrow" not in svg


def test_a_zero_width_plot_renders_instead_of_dividing_by_zero() -> None:
    # width 94 is exactly the padding: the group slot is 0 and the stride guard is all
    # that stands between it and ZeroDivisionError.
    svg = _chart(("a", "b"), width=94)
    assert svg.rstrip().endswith("</svg>")


@pytest.mark.parametrize(
    ("n", "every", "labelled"),
    [
        # Rotated labels need ~34.7px of pitch. 626/40 = 15.65px -> every 3rd (2.2, ceil 3).
        (40, 3, 14),
        # 626/20 = 31.3px -> 1.1, ceil 2: just short of one label per bar.
        (20, 2, 10),
    ],
)
def test_rotated_labels_thin_to_exactly_the_stated_stride(
    n: int, every: int, labelled: int
) -> None:
    svg = _chart(tuple(f"candidate-{i:03d}" for i in range(n)), width=720)
    assert svg.count("rotate(-22 ") == labelled
    assert f"every {_ordinal(every)} of {n} bars is labelled" in svg


def test_rotated_labels_at_full_pitch_are_all_drawn() -> None:
    # 626/18 = 34.8px clears the 34.7px rotated pitch: every label prints, no caption.
    n = 18
    svg = _chart(tuple(f"candidate-{i:03d}" for i in range(n)), width=720)
    assert svg.count("rotate(-22 ") == n
    assert "is labelled" not in svg


def test_axis_top_follows_the_largest_value_including_reference_lines() -> None:
    # Data tops out at 0.5; a reference line at 3 must still be on the chart -> axis 0..5.
    svg = _chart(("a", "b"), width=720, reference_lines=(ReferenceLine(3.0, "cap"),))
    assert 'text-anchor="end">5</text>' in svg
    # And the largest bar, not the smallest, sets it.
    svg = bar_chart(title="T", categories=("a", "b"), series=(Series("s", (3.0, 37.0), "#000"),))
    assert 'text-anchor="end">50</text>' in svg


def test_axis_bottom_reaches_a_negative_value_below_the_floor() -> None:
    # y_min defaults to 0; a -0.5 bar must pull the axis down to it, not be clipped.
    svg = bar_chart(title="T", categories=("a", "b"), series=(Series("s", (-0.5, 0.3), "#000"),))
    assert 'text-anchor="end">-0.5</text>' in svg
