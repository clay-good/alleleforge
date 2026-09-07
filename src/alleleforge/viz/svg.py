"""A tiny, dependency-free SVG bar-chart renderer.

AlleleForge ships **committed, reproducible figures** for its docs and preprint
without pulling a plotting stack (matplotlib/plotly) into the dependency tree —
the same hand-rolled-renderer discipline as :mod:`alleleforge.report.pdf`. Output
is a deterministic SVG string (no timestamps, no random ids, fixed number
formatting), so a figure re-renders byte-for-byte and is safe to diff and commit.

One function does the work: :func:`bar_chart` draws one or more value series across
named categories (grouped bars when there is more than one series), with optional
dashed reference lines (a calibration threshold, a coverage target) and value
labels atop every bar.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

#: A color is a hex triplet/quad/6/8-digit (`#rgb`…`#rrggbbaa`) or a bare CSS name.
#: Colors are interpolated into SVG `fill=`/`stroke=` **attributes**, which `_esc`
#: (scoped to text nodes) does not cover — so a color carrying `"`/`<`/`>`/`&` would
#: break out of the attribute (the R12 injection class, on the one caller-controlled
#: value that reaches an attribute). A legitimate color never contains markup, so it
#: is validated at construction rather than escaped.
_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{3,8}$|^[a-zA-Z]+$")


def _check_color(color: str) -> str:
    """Return ``color`` if it is a safe hex/named color, else raise ``ValueError``."""
    if not _COLOR_RE.fullmatch(color):
        raise ValueError(f"invalid color {color!r}: expected a hex code or a CSS color name")
    return color


#: X-axis label rotation, in degrees, and the pitch two rotated labels need to clear each
#: other. Rotated labels are parallel lines of text: they collide when the *perpendicular*
#: distance between their baselines falls below a line height, and that distance is
#: `pitch * sin(theta)` — independent of how long the labels are. At -22° and a 13px line
#: this is about 35px. Modelling it as a fraction of the upright width instead hid half
#: the labels on a five-bar chart whose category names happen to be long, which is exactly
#: what rotation exists to avoid.
_ROTATION_DEG = 22.0
_ROTATED_MIN_PITCH = 13.0 / math.sin(math.radians(_ROTATION_DEG))

#: Below this group slot (px) a per-bar value label cannot avoid its neighbour, so it is
#: not drawn. Two four-character numbers need roughly this much to sit side by side.
_MIN_SLOT_FOR_VALUE_LABEL = 26.0

#: Slate ink for axes, labels, and the frame.
_INK = "#1f2933"
#: Muted ink for secondary labels (subtitle, axis ticks).
_MUTED = "#62707d"
#: Hairline grey for gridlines.
_GRID = "#dde3e8"
#: The default qualitative series palette (color-blind-safe order).
PALETTE: tuple[str, ...] = ("#2b6cb0", "#dd6b20", "#38a169", "#805ad5", "#d53f8c")


@dataclass(frozen=True)
class Series:
    """One named, colored value series, one value per category."""

    name: str
    values: tuple[float, ...]
    color: str

    def __post_init__(self) -> None:
        """Reject a color that could break out of the SVG `fill=` attribute."""
        _check_color(self.color)


@dataclass(frozen=True)
class ReferenceLine:
    """A horizontal dashed annotation line at ``value`` on the y-axis."""

    value: float
    label: str
    color: str = "#e53e3e"

    def __post_init__(self) -> None:
        """Reject a color that could break out of the SVG `stroke=` attribute."""
        _check_color(self.color)


def _fmt(value: float) -> str:
    """Format a number deterministically: drop a trailing ``.0``, else 3 dp."""
    rounded = round(value, 3)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:g}"


def _esc(text: str) -> str:
    """Escape text for an SVG text node."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


#: Line height of a wrapped subtitle line, in px.
_SUBTITLE_LINE_H = 15

#: Average glyph advance at font-size 12, for wrapping the subtitle.
_SUBTITLE_CHAR_W = 5.7


def _wrap_subtitle(text: str, width_px: float) -> list[str]:
    """Return ``text`` broken into lines that fit ``width_px``.

    Word-wrapped on spaces at an estimated glyph advance — the renderer has no font
    metrics and does not need them: erring narrow leaves white space, erring wide runs
    text off the image, which is what the unwrapped version did.
    """
    if not text:
        return []
    limit = max(20, int(width_px / _SUBTITLE_CHAR_W))
    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > limit:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _ordinal(n: int) -> str:
    """Return ``n`` as an English ordinal (``2nd``, ``3rd``, ``11th``)."""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _nice_max(value: float) -> float:
    """Round a positive axis maximum up to a clean 1/2/5 × 10ⁿ step."""
    if value <= 0:
        return 1.0
    from math import floor, log10

    magnitude = 10.0 ** floor(log10(value))
    for step in (1.0, 2.0, 2.5, 5.0, 10.0):
        candidate = step * magnitude
        if candidate >= value:
            return candidate
    return 10.0 * magnitude  # pragma: no cover - the 10.0 step always catches first


def bar_chart(
    *,
    title: str,
    categories: tuple[str, ...],
    series: tuple[Series, ...],
    subtitle: str = "",
    y_label: str = "",
    y_max: float | None = None,
    y_min: float = 0.0,
    value_suffix: str = "",
    reference_lines: tuple[ReferenceLine, ...] = (),
    width: int = 720,
    height: int = 380,
) -> str:
    """Render a grouped bar chart to a standalone, deterministic SVG string.

    Args:
        title: Bold chart title.
        categories: One x-axis label per group.
        series: One or more value series (grouped side by side within each
            category); each must have one value per category.
        subtitle: A smaller line under the title (units, source, caveat).
        y_label: Rotated y-axis caption.
        y_max: Fixed axis maximum; when ``None`` it is derived from the data
            (rounded up to a clean step, or to ``1.0`` when all values are ≤ 1).
        y_min: Axis minimum (use a negative value for signed quantities like a gap).
        value_suffix: Appended to every bar's value label (e.g. ``"%"``).
        reference_lines: Dashed horizontal annotation lines.
        width: SVG width in px.
        height: SVG height in px.

    Returns:
        A complete ``<svg>…</svg>`` document.

    Raises:
        ValueError: If a series length does not match the category count.
    """
    for s in series:
        if len(s.values) != len(categories):
            raise ValueError(
                f"series {s.name!r} has {len(s.values)} values, {len(categories)} cats"
            )

    # Rotate x labels when the longest would overrun its group slot (~6.5px/char).
    group_slot = (width - 70 - 24) / max(len(categories), 1)
    longest = max((len(c) for c in categories), default=0)
    rotate_x = longest * 6.5 > group_slot
    # Rotation buys ~1/cos(22°) of horizontal room and no more. Past that the labels
    # simply overlap: a 90-candidate menu — an ordinary prime design — gave 6.9px of
    # slot for labels 44px wide, and the per-bar value labels landed at 0.0px spacing,
    # printed on top of one another. That is the report's headline figure. Every other
    # capped thing here states what it withheld, so the chart labels every k-th category
    # and says which k, rather than drawing an unreadable smear or silently dropping
    # bars — the bars are the distribution and they all stay.
    needed = _ROTATED_MIN_PITCH if rotate_x else longest * 6.5
    label_every = max(1, math.ceil(needed / group_slot)) if group_slot > 0 else 1
    # A value printed over its neighbour is worse than no value; the number is on the
    # candidate's own row either way.
    show_values = group_slot >= _MIN_SLOT_FOR_VALUE_LABEL
    pad_left, pad_right = 70, 24
    pad_bottom = 96 if rotate_x else 70
    plot_w = width - pad_left - pad_right

    # A thinned axis states its own thinning, in the same line the caller's caveats are
    # in: a reader counting bars against labels must not have to infer the ratio.
    crowding = ""
    if label_every > 1:
        crowding = (
            f"every {_ordinal(label_every)} of {len(categories)} bars is labelled "
            "(the rest are drawn but too narrow to label)"
        )
    elif not show_values and len(categories) > 1:
        crowding = f"all {len(categories)} bars are drawn; too narrow to print each value"
    # Wrapped, and the plot moved down to make room. This line was drawn as one unwrapped
    # `<text>`: the design report's subtitle carries the calibration and trained-model
    # qualifiers and had already reached 243 characters — about 1,360px in a 720px chart,
    # running 735px past the right edge and off the image. The honest caption was
    # invisible past the first two thirds.
    subtitle_lines = _wrap_subtitle(
        "; ".join(part for part in (subtitle, crowding) if part), plot_w
    )
    pad_top = 64 + _SUBTITLE_LINE_H * max(0, len(subtitle_lines) - 1)
    plot_h = height - pad_top - pad_bottom

    all_values = [v for s in series for v in s.values] + [r.value for r in reference_lines]
    hi = y_max if y_max is not None else _nice_max(max(all_values + [y_min], default=1.0))
    lo = min(y_min, min(all_values, default=0.0))
    span = hi - lo or 1.0

    def y_px(value: float) -> float:
        return pad_top + plot_h * (1.0 - (value - lo) / span)

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="-apple-system,Segoe UI,Roboto,sans-serif">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="{pad_left}" y="28" fill="{_INK}" font-size="17" font-weight="700">'
        f"{_esc(title)}</text>",
    ]
    for i, line in enumerate(subtitle_lines):
        parts.append(
            f'<text x="{pad_left}" y="{47 + i * _SUBTITLE_LINE_H}" fill="{_MUTED}" '
            f'font-size="12">{_esc(line)}</text>'
        )

    # Horizontal gridlines + y tick labels (5 steps).
    for i in range(6):
        value = lo + span * i / 5
        gy = y_px(value)
        parts.append(
            f'<line x1="{pad_left}" y1="{gy:.1f}" x2="{pad_left + plot_w}" y2="{gy:.1f}" '
            f'stroke="{_GRID}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{pad_left - 8}" y="{gy + 4:.1f}" fill="{_MUTED}" font-size="11" '
            f'text-anchor="end">{_fmt(value)}</text>'
        )
    if y_label:
        cy = pad_top + plot_h / 2
        parts.append(
            f'<text x="18" y="{cy:.1f}" fill="{_MUTED}" font-size="12" text-anchor="middle" '
            f'transform="rotate(-90 18 {cy:.1f})">{_esc(y_label)}</text>'
        )

    # Zero baseline (emphasized when the axis spans negatives).
    if lo < 0 < hi:
        zy = y_px(0.0)
        parts.append(
            f'<line x1="{pad_left}" y1="{zy:.1f}" x2="{pad_left + plot_w}" y2="{zy:.1f}" '
            f'stroke="{_INK}" stroke-width="1"/>'
        )

    # Bars, grouped per category.
    n_groups = len(categories)
    group_w = plot_w / n_groups
    n_series = len(series)
    bar_gap = group_w * 0.18
    bar_w = (group_w - bar_gap) / n_series
    base_y = y_px(max(lo, 0.0))
    for gi, label in enumerate(categories):
        gx = pad_left + gi * group_w
        for si, s in enumerate(series):
            value = s.values[gi]
            bx = gx + bar_gap / 2 + si * bar_w
            top = y_px(max(value, 0.0)) if value >= 0 else base_y
            bottom = base_y if value >= 0 else y_px(value)
            bar_h = max(bottom - top, 0.0)
            parts.append(
                f'<rect x="{bx + 2:.1f}" y="{top:.1f}" width="{bar_w - 4:.1f}" '
                f'height="{bar_h:.1f}" fill="{s.color}" rx="2"/>'
            )
            if show_values:
                label_y = (top - 6) if value >= 0 else (bottom + 14)
                parts.append(
                    f'<text x="{bx + bar_w / 2:.1f}" y="{label_y:.1f}" fill="{_INK}" '
                    f'font-size="11" font-weight="600" text-anchor="middle">'
                    f"{_fmt(value)}{_esc(value_suffix)}</text>"
                )
        cx = gx + group_w / 2
        ly = height - pad_bottom + 18
        if gi % label_every:
            continue
        if rotate_x:
            parts.append(
                f'<text x="{cx:.1f}" y="{ly:.1f}" fill="{_INK}" font-size="11" text-anchor="end" '
                f'transform="rotate(-22 {cx:.1f} {ly:.1f})">{_esc(label)}</text>'
            )
        else:
            parts.append(
                f'<text x="{cx:.1f}" y="{ly:.1f}" fill="{_INK}" font-size="12" '
                f'text-anchor="middle">{_esc(label)}</text>'
            )

    # Dashed reference lines, drawn over the bars.
    for ref in reference_lines:
        ry = y_px(ref.value)
        parts.append(
            f'<line x1="{pad_left}" y1="{ry:.1f}" x2="{pad_left + plot_w}" y2="{ry:.1f}" '
            f'stroke="{ref.color}" stroke-width="1.5" stroke-dasharray="6 4"/>'
        )
        # A white halo keeps the label legible where it crosses a bar.
        text_w = len(ref.label) * 6.4
        right = pad_left + plot_w
        parts.append(
            f'<rect x="{right - text_w - 3:.1f}" y="{ry - 16:.1f}" width="{text_w + 6:.1f}" '
            f'height="14" fill="#ffffff" opacity="0.82"/>'
        )
        parts.append(
            f'<text x="{right:.1f}" y="{ry - 5:.1f}" fill="{ref.color}" font-size="11" '
            f'text-anchor="end">{_esc(ref.label)}</text>'
        )

    # Legend (only when more than one series).
    if n_series > 1:
        lx = pad_left
        ly = height - 22
        for s in series:
            parts.append(
                f'<rect x="{lx}" y="{ly - 9}" width="12" height="12" fill="{s.color}" rx="2"/>'
            )
            parts.append(
                f'<text x="{lx + 17}" y="{ly + 1}" fill="{_INK}" font-size="12">'
                f"{_esc(s.name)}</text>"
            )
            lx += 24 + 7 * len(s.name)

    parts.append("</svg>")
    return "\n".join(parts) + "\n"
