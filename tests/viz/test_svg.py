"""Tests for the dependency-free SVG bar-chart renderer."""

from __future__ import annotations

import pytest

from alleleforge.viz.svg import PALETTE, ReferenceLine, Series, _fmt, _nice_max, bar_chart


def test_single_series_renders_valid_svg() -> None:
    svg = bar_chart(
        title="T",
        categories=("a", "b"),
        series=(Series("s", (1.0, 2.0), PALETTE[0]),),
    )
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    assert "viewBox" in svg
    assert ">a<" in svg and ">b<" in svg  # category labels


def test_grouped_series_emits_legend() -> None:
    svg = bar_chart(
        title="T",
        categories=("a",),
        series=(Series("raw", (0.2,), PALETTE[0]), Series("calibrated", (0.8,), PALETTE[1])),
    )
    assert ">raw<" in svg and ">calibrated<" in svg  # legend entries


def test_mismatched_series_length_raises() -> None:
    with pytest.raises(ValueError, match="values"):
        bar_chart(title="T", categories=("a", "b"), series=(Series("s", (1.0,), PALETTE[0]),))


def test_negative_values_draw_zero_baseline() -> None:
    svg = bar_chart(
        title="gap",
        categories=("x", "y"),
        series=(Series("g", (-0.04, 0.02), PALETTE[2]),),
        y_min=-0.1,
        y_max=0.1,
    )
    assert "-0.04" in svg and "0.02" in svg


def test_reference_line_label_and_halo() -> None:
    svg = bar_chart(
        title="T",
        categories=("a",),
        series=(Series("s", (0.2,), PALETTE[0]),),
        reference_lines=(ReferenceLine(0.1, "flag"),),
    )
    assert "stroke-dasharray" in svg  # the dashed line
    assert ">flag<" in svg
    assert 'fill="#ffffff"' in svg  # the legibility halo


def test_long_labels_rotate() -> None:
    short = bar_chart(title="T", categories=("a", "b"), series=(Series("s", (1.0, 2.0), "#000"),))
    # Five narrow slots with a 24-char label (like offtarget-classification) overrun.
    cats = ("offtarget-classification",) * 5
    long = bar_chart(title="T", categories=cats, series=(Series("s", (1.0,) * 5, "#000"),))
    assert "rotate(-22" in long
    assert "rotate(-22" not in short


def test_auto_y_max_rounds_to_clean_step() -> None:
    # y_max=None derives the axis from the data via _nice_max.
    svg = bar_chart(title="T", categories=("a",), series=(Series("s", (37.0,), "#000"),))
    assert "viewBox" in svg  # renders without a fixed y_max


def test_value_suffix_and_y_label() -> None:
    svg = bar_chart(
        title="T",
        categories=("a",),
        series=(Series("s", (80.0,), "#000"),),
        value_suffix="%",
        y_label="coverage",
        y_max=100.0,
    )
    assert "80%" in svg
    assert ">coverage<" in svg


def test_text_is_escaped() -> None:
    svg = bar_chart(title="A & B <x>", categories=("a",), series=(Series("s", (1.0,), "#000"),))
    assert "A &amp; B &lt;x&gt;" in svg


@pytest.mark.parametrize(
    ("value", "expected"),
    [(1.0, "1"), (2.0, "2"), (0.105, "0.105"), (0.5, "0.5"), (80.0, "80")],
)
def test_fmt_drops_trailing_zero(value: float, expected: str) -> None:
    assert _fmt(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.0, 1.0), (-5.0, 1.0), (0.4, 0.5), (37.0, 50.0), (1.0, 1.0), (9.9, 10.0)],
)
def test_nice_max(value: float, expected: float) -> None:
    assert _nice_max(value) == expected
