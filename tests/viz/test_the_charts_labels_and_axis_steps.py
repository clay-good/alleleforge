"""The chart's ordinal label, its axis steps, and the immutability of its inputs.

`_ordinal` writes the stride into the caption a reader counts bars against: "every 21st of
90 bars is labelled". Its `10 <= n % 100 <= 20` window is the English teens exception, and
the upper bound could move to 21 with the suite green — the caption would then read "every
21th", because the only strides any fixture ever produced were 2 and 10. The stride is
`ceil(needed / group_slot)` on a real menu, so a two-digit one is ordinary rather than
contrived.

`_nice_max` is documented as rounding up to "a clean 1/2/5 x 10^n step", and the existing
parametrized cases are 0.4, 1.0, 9.9, 37.0 and two non-positives. None of them lands in
the band that selects the `2.0` step, so that step could become 2.2 — an axis maximum that
is not a clean step at all — and nothing failed. Tested here as the property the docstring
states rather than as more rows, so every step is covered at once.
"""

from __future__ import annotations

import dataclasses
import math
import re

import pytest

from alleleforge.viz import svg
from alleleforge.viz.svg import ReferenceLine, Series, _nice_max, _ordinal

#: The clean steps `_nice_max`'s docstring promises, per decade.
_STEPS = (1.0, 2.0, 2.5, 5.0, 10.0)


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (1, "1st"),
        (2, "2nd"),
        (3, "3rd"),
        (4, "4th"),
        (10, "10th"),
        (11, "11th"),  # the teens exception, not "11st"
        (12, "12th"),
        (13, "13th"),
        (14, "14th"),
        (20, "20th"),
        (21, "21st"),  # out of the exception again: the upper bound of the window
        (22, "22nd"),
        (23, "23rd"),
        (100, "100th"),
        (101, "101st"),
        (111, "111th"),  # 111 % 100 == 11, still a teen
        (121, "121st"),
    ],
)
def test_the_stride_is_written_as_a_correct_english_ordinal(n: int, expected: str) -> None:
    assert _ordinal(n) == expected


# --- the axis step ------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [0.04, 0.4, 0.9, 1.0, 1.2, 1.5, 2.0, 2.1, 2.5, 3.0, 4.9, 5.0, 7.5, 9.9, 12.0, 37.0, 180.0],
)
def test_the_axis_maximum_is_the_smallest_clean_step_that_covers_the_data(
    value: float,
) -> None:
    result = _nice_max(value)
    assert result >= value, "an axis that does not reach the data clips a bar"
    decade = 10.0 ** math.floor(math.log10(value))
    allowed = sorted(step * decade for step in _STEPS)
    assert result == pytest.approx(min(c for c in allowed if c >= value)), (
        f"_nice_max({value}) = {result}, which is not the smallest of {allowed} "
        "that covers the value"
    )


@pytest.mark.parametrize("value", [1.2, 1.5, 2.0])
def test_a_value_in_the_two_step_band_lands_on_two(value: float) -> None:
    """The band no existing fixture reached, named explicitly so it stays covered."""
    assert _nice_max(value) == 2.0


def test_a_non_positive_axis_maximum_falls_back_to_one() -> None:
    assert _nice_max(0.0) == 1.0
    assert _nice_max(-5.0) == 1.0


# --- the chart's inputs ------------------------------------------------------------


def _chart_dataclasses() -> list[type]:
    found = [
        obj
        for name, obj in vars(svg).items()
        if isinstance(obj, type)
        and dataclasses.is_dataclass(obj)
        and obj.__module__ == svg.__name__
        and not name.startswith("_")
    ]
    assert found, "no chart dataclasses discovered; this test would pass vacuously"
    return found


def test_the_chart_dataclasses_this_covers_are_still_there() -> None:
    assert {"Series", "ReferenceLine"} <= {c.__name__ for c in _chart_dataclasses()}


@pytest.mark.parametrize("cls", _chart_dataclasses(), ids=lambda c: c.__name__)
def test_a_chart_input_cannot_be_retuned_after_validation(cls: type) -> None:
    """`Series.__post_init__` rejects a color that breaks out of the SVG attribute.

    That check runs once, at construction. Unfrozen, a caller could assign the
    rejected value afterwards and the escape would reach the rendered document, so
    the frozen declaration is what makes the validation worth anything.
    """
    assert cls.__dataclass_params__.frozen is True


def test_a_series_colour_cannot_be_swapped_for_one_that_escapes_the_attribute() -> None:
    series = Series(name="s", values=(1.0,), color="#112233")
    with pytest.raises(dataclasses.FrozenInstanceError):
        series.color = '" onload="alert(1)'  # type: ignore[misc]
    with pytest.raises(ValueError, match="colour|color"):
        Series(name="s", values=(1.0,), color='" onload="alert(1)')


def test_a_reference_line_cannot_be_moved_after_the_chart_reads_it() -> None:
    line = ReferenceLine(value=0.5, label="baseline")
    with pytest.raises(dataclasses.FrozenInstanceError):
        line.value = 99.0  # type: ignore[misc]


# --- the uncrowded chart: the negative case for every thinning rule ----------------


def _chart(categories: tuple[str, ...], width: int) -> str:
    return svg.bar_chart(
        title="T",
        categories=categories,
        series=(Series("s", tuple(0.5 for _ in categories), "#000"),),
        width=width,
    )


def test_a_roomy_chart_labels_every_bar_and_claims_no_thinning() -> None:
    """The stride floor is 1, and every crowding test so far was a crowded chart.

    `label_every = max(1, ceil(needed / group_slot))` could floor at 2 instead, and
    then *every* chart — however much room it has — would label half its bars and
    print "every 2nd of N bars is labelled". Each existing fixture is already past a
    crowding threshold, so each one expects a stride above 1 and cannot tell a floor
    of 1 from a floor of 2.
    """
    svg_text = _chart(("a", "b", "c"), width=720)
    assert "bars is labelled" not in svg_text, (
        "a three-bar chart in a 720px frame has room for every label; claiming to "
        "have thinned is a false caveat"
    )
    assert "too narrow to print each value" not in svg_text
    for category in ("a", "b", "c"):
        assert f">{category}<" in svg_text, f"{category} was not labelled"


def _caption(svg_text: str) -> str:
    """Return the chart's text content as one normalized line.

    A narrow chart wraps its caption to the frame, one or two words per `<text>`, so a
    phrase assertion against the raw markup is blind exactly where a narrow-chart test
    needs to look. Join the runs and collapse the whitespace instead.
    """
    runs = re.findall(r"<text[^>]*>(.*?)</text>", svg_text, flags=re.DOTALL)
    return " ".join(" ".join(runs).split())


def test_two_bars_too_narrow_for_values_still_say_so() -> None:
    """`len(categories) > 1` is the guard; two is the smallest collection it admits.

    A single bar needs no such note — there is nothing to crowd against — but two do,
    and a fixture with more than two cannot distinguish `> 1` from `> 2`.
    """
    caption = _caption(_chart(("a", "b"), width=144))
    assert "all 2 bars are drawn; too narrow to print each value" in caption


def test_one_bar_never_claims_crowding() -> None:
    """The other side of the same guard: one bar is not a crowd."""
    assert "bars are drawn" not in _caption(_chart(("a",), width=144))


def test_a_frame_with_no_room_at_all_still_labels_every_bar() -> None:
    """`group_slot <= 0` is reachable: the frame has no validator, and 94px is the
    padding alone, so any width at or below it leaves a non-positive slot.

    The stride then falls back to 1 rather than being computed from a division by a
    non-positive number. A fallback of 2 would print "every 2nd of 1 bars is
    labelled" over a single-bar chart — a thinning claim about a chart with nothing
    to thin — and every other fixture here has a positive slot, so none of them can
    reach the branch.
    """
    caption = _caption(_chart(("a",), width=94))
    assert "bars is labelled" not in caption, "nothing was thinned; claiming it is false"
    assert ">a<" in _chart(("a",), width=94), "the one bar keeps its label"
