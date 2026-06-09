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

from dataclasses import dataclass

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


@dataclass(frozen=True)
class ReferenceLine:
    """A horizontal dashed annotation line at ``value`` on the y-axis."""

    value: float
    label: str
    color: str = "#e53e3e"


def _fmt(value: float) -> str:
    """Format a number deterministically: drop a trailing ``.0``, else 3 dp."""
    rounded = round(value, 3)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:g}"


def _esc(text: str) -> str:
    """Escape text for an SVG text node."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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
    pad_left, pad_right, pad_top = 70, 24, 64
    pad_bottom = 96 if rotate_x else 70
    plot_w = width - pad_left - pad_right
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
    if subtitle:
        parts.append(
            f'<text x="{pad_left}" y="47" fill="{_MUTED}" font-size="12">{_esc(subtitle)}</text>'
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
            label_y = (top - 6) if value >= 0 else (bottom + 14)
            parts.append(
                f'<text x="{bx + bar_w / 2:.1f}" y="{label_y:.1f}" fill="{_INK}" font-size="11" '
                f'font-weight="600" text-anchor="middle">{_fmt(value)}{value_suffix}</text>'
            )
        cx = gx + group_w / 2
        ly = height - pad_bottom + 18
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
