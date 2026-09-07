"""The report's headline figure was an unreadable smear, and its caption ran off the image.

Measured on an ordinary 90-candidate prime menu — the routine size for this chemistry,
since every PBS x RTT-homology x PAM combination is a distinct pegRNA:

    90 x-axis labels at 6.9px pitch, each ~44px wide even rotated
    95 value labels, minimum x-spacing 0.0px — printed on top of one another
    subtitle 243 characters ~ 1,360px, in a 720px chart: 735px off the right edge

Rotation was the renderer's only crowding relief and is worth about 7%. Past that the
labels simply overlapped, and the subtitle — which carries the calibration and
trained-model qualifiers this project works hardest to put there — was invisible past its
first two thirds.

The bars are the distribution and all of them stay. What is capped is the *labelling*, and
the chart says which: "every 8th of 90 bars is labelled". The subtitle wraps and the plot
moves down to make room.
"""

from __future__ import annotations

import re

import pytest

from alleleforge.viz.svg import _ROTATED_MIN_PITCH, Series, bar_chart

#: Rough glyph advance for the label font sizes this renderer uses.
_LABEL_CHAR_W = 6.5
_SUBTITLE_CHAR_W = 5.7


def _chart(n: int, subtitle: str = "point estimate", width: int = 720) -> str:
    return bar_chart(
        title="Predicted efficiency",
        subtitle=subtitle,
        categories=tuple(f"#{i + 1} prime" for i in range(n)),
        series=(Series(name="efficiency", values=tuple(0.5 for _ in range(n)), color="#0a7d77"),),
        width=width,
    )


def _label_xs(svg: str, prefix: str = "#") -> list[float]:
    return sorted(
        float(m.group(1))
        for m in re.finditer(r'<text x="([\d.]+)"[^>]*>([^<]*)</text>', svg)
        if m.group(2).startswith(prefix)
    )


def _subtitle_lines(svg: str) -> list[str]:
    return [
        m.group(1)
        for m in re.finditer(
            r'<text x="\d+" y="\d+" fill="#62707d" font-size="12">([^<]*)</text>', svg
        )
    ]


@pytest.mark.parametrize("n", [3, 12, 50, 90, 300])
def test_drawn_labels_never_overlap(n: int) -> None:
    svg = _chart(n)
    xs = _label_xs(svg)
    assert xs, f"no x labels drawn for {n} categories"
    gaps = [b - a for a, b in zip(xs, xs[1:], strict=False)]
    if not gaps:
        return
    upright = max(len(f"#{i + 1} prime") for i in range(n)) * _LABEL_CHAR_W
    # Rotated labels are parallel lines of text and collide by *perpendicular* distance,
    # which is `pitch * sin(22°)`; upright ones collide by width. Checking the wrong one
    # is not a stricter test, it is a different one — modelling rotation as a fraction of
    # the upright width hid half the labels on a five-bar chart.
    needed = _ROTATED_MIN_PITCH if "rotate(-22" in svg else upright
    assert min(gaps) >= needed * 0.95, (n, min(gaps), needed)


@pytest.mark.parametrize("n", [3, 12, 50, 90, 300])
def test_every_bar_is_still_drawn(n: int) -> None:
    """Thinning the labels must not thin the data."""
    svg = _chart(n)
    # One background rect plus one per bar.
    assert svg.count("<rect") == n + 1, n


def test_a_thinned_axis_says_so() -> None:
    svg = _chart(90)
    assert "every 5th of 90 bars is labelled" in svg, _subtitle_lines(svg)


def test_a_five_bar_chart_with_long_names_labels_all_five() -> None:
    """Rotation exists to make long names fit; thinning them defeats it.

    The committed benchmark figures are exactly this shape — five tasks, names like
    `offtarget-classification` — and a width-based rule dropped every other one.
    """
    names = (
        "offtarget-classification",
        "cas9-efficiency",
        "pe-efficiency",
        "be-outcome",
        "cas9-outcome",
    )
    svg = bar_chart(
        title="Per-task calibration error",
        categories=names,
        series=(Series(name="ece", values=(0.1,) * 5, color="#0a7d77"),),
    )
    drawn = [n for n in names if f">{n}<" in svg]
    assert drawn == list(names), drawn
    assert "is labelled" not in svg


def test_an_uncrowded_axis_says_nothing_about_thinning() -> None:
    """A caption that always explains itself is a caption nobody reads."""
    svg = _chart(4)
    assert "is labelled" not in svg
    assert len(_label_xs(svg)) == 4


def test_value_labels_are_dropped_rather_than_stacked() -> None:
    """A number printed over its neighbour is worse than no number."""
    crowded = _chart(90)
    values = re.findall(r'font-size="11" font-weight="600"', crowded)
    assert not values, f"{len(values)} value labels on a 90-bar chart"
    roomy = _chart(6)
    assert re.findall(r'font-size="11" font-weight="600"', roomy)


@pytest.mark.parametrize("width", [520, 720, 960])
def test_the_subtitle_stays_inside_the_plot(width: int) -> None:
    long_subtitle = (
        "point estimate; the 80% interval is printed beside each candidate; intervals "
        "are nominal, coverage not measured; heuristic point estimates, not from a "
        "trained model"
    )
    svg = _chart(90, subtitle=long_subtitle, width=width)
    lines = _subtitle_lines(svg)
    assert len(lines) > 1, "the long subtitle was not wrapped"
    usable = width - 70 - 24
    for line in lines:
        assert len(line) * _SUBTITLE_CHAR_W <= usable + 1, (width, len(line), line)
    assert " ".join(lines).startswith("point estimate"), lines


def test_wrapping_the_subtitle_does_not_push_the_plot_off_the_image() -> None:
    """Room is made by moving the plot down, not by drawing past the bottom edge."""
    svg = _chart(90, subtitle="a " * 120)
    height = int(re.search(r'height="(\d+)"', svg).group(1))
    ys = [float(m.group(1)) for m in re.finditer(r'<line[^>]*y1="([\d.]+)"', svg)]
    assert ys and max(ys) < height, (max(ys), height)
