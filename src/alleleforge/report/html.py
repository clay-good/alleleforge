"""Render a design report as a self-contained, interactive HTML page.

The HTML leads with the research-use disclaimer and ends with provenance, as the
spec requires. Charts are **interactive Plotly** figures: the Plotly library is
pulled from its CDN (a static script, never sequence data) and each figure's
spec is inlined as JSON, so the page needs no Python plotting dependency and no
network access for the *data*. Off-target tables are ancestry-stratified.

No sequence data ever leaves the page: everything is inlined into the single
HTML file the caller writes wherever they choose.
"""

from __future__ import annotations

import html
import json
from typing import Any

from alleleforge.report.builder import CandidateReport, DesignReport

#: Pinned Plotly CDN bundle (the plotting library only — no data leaves).
PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.35.2.min.js"

_STYLE = """
:root { --teal:#0a7d77; --ink:#1a1a1a; --muted:#666; --line:#e2e2e2; }
* { box-sizing: border-box; }
body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; color: var(--ink);
       margin: 0; padding: 0 1.5rem 4rem; line-height: 1.5; }
header { padding: 1.5rem 0 0.5rem; }
h1 { color: var(--teal); margin: 0 0 0.25rem; }
.disclaimer { background:#fff8e6; border:1px solid #e8c96b; border-radius:8px;
              padding:0.9rem 1.1rem; margin:1rem 0; font-size:0.92rem; }
.candidate { border:1px solid var(--line); border-radius:10px; padding:1rem 1.2rem;
             margin:1rem 0; }
.candidate h3 { margin:0 0 0.3rem; }
.badge { display:inline-block; font-size:0.72rem; font-weight:600; padding:0.1rem 0.5rem;
         border-radius:999px; background:var(--teal); color:#fff; margin-left:0.5rem; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size:0.85rem; }
table { border-collapse: collapse; margin:0.5rem 0; font-size:0.88rem; }
th, td { border:1px solid var(--line); padding:0.3rem 0.6rem; text-align:left; }
th { background:#f4f9f8; }
.muted { color: var(--muted); font-size:0.85rem; }
.chart { width:100%; max-width:760px; height:320px; }
footer { margin-top:2rem; border-top:1px solid var(--line); padding-top:1rem;
         font-size:0.8rem; color: var(--muted); }
""".strip()


def _esc(text: object) -> str:
    """HTML-escape any value's string form."""
    return html.escape(str(text))


def _efficiency_figure(report: DesignReport) -> dict[str, Any] | None:
    """Build a Plotly bar figure of efficiency (with interval error bars)."""
    xs, ys, lo, hi = [], [], [], []
    for c in report.candidates:
        if c.efficiency is None:
            continue
        xs.append(f"#{c.rank} {c.chemistry.value}")
        ys.append(round(c.efficiency.value, 4))
        lo.append(round(c.efficiency.value - c.efficiency.interval[0], 4))
        hi.append(round(c.efficiency.interval[1] - c.efficiency.value, 4))
    if not xs:
        return None
    return {
        "data": [
            {
                "type": "bar",
                "x": xs,
                "y": ys,
                "error_y": {"type": "data", "symmetric": False, "array": hi, "arrayminus": lo},
                "marker": {"color": "#0a7d77"},
                "name": "efficiency",
            }
        ],
        "layout": {
            "title": "Calibrated efficiency (80% interval)",
            "yaxis": {"title": "efficiency", "range": [0, 1]},
            "margin": {"t": 40, "r": 10, "b": 80, "l": 50},
        },
    }


def _offtarget_figure(report: DesignReport) -> dict[str, Any] | None:
    """Build a grouped Plotly bar of worst-case off-target score per ancestry."""
    ancestries: list[str] = []
    for c in report.candidates:
        for row in c.offtarget_by_ancestry:
            if row.ancestry not in ancestries:
                ancestries.append(row.ancestry)
    if not ancestries:
        return None
    traces = []
    for c in report.candidates:
        by = {r.ancestry: r.worst_score for r in c.offtarget_by_ancestry}
        traces.append(
            {
                "type": "bar",
                "name": f"#{c.rank} {c.chemistry.value}",
                "x": ancestries,
                "y": [round(by.get(a, 0.0), 4) for a in ancestries],
            }
        )
    return {
        "data": traces,
        "layout": {
            "title": "Worst-case off-target score by ancestry",
            "barmode": "group",
            "yaxis": {"title": "off-target score", "range": [0, 1]},
            "margin": {"t": 40, "r": 10, "b": 50, "l": 50},
        },
    }


def _candidate_html(c: CandidateReport) -> str:
    """Render one candidate block."""
    badge = '<span class="badge">Pareto</span>' if c.on_pareto_front else ""
    parts = [f"<div class='candidate'><h3>#{c.rank} · {_esc(c.chemistry.value)}{badge}</h3>"]
    parts.append(f"<div class='mono'>{_esc(c.reagent)}</div>")
    if c.efficiency is not None:
        e = c.efficiency
        ood = "" if e.in_distribution else " <strong>(out-of-distribution)</strong>"
        parts.append(
            f"<p>Efficiency <strong>{e.value:.2f}</strong> "
            f"[{e.interval[0]:.2f}, {e.interval[1]:.2f}] @ {e.interval_level:.0%}{ood}</p>"
        )
    if c.p_intended is not None:
        parts.append(f"<p>P(intended) = <strong>{c.p_intended:.2f}</strong></p>")
    if c.outcome_top:
        rows = "".join(
            f"<tr><td class='mono'>{_esc(a.allele)}</td><td>{a.probability:.3f}</td>"
            f"<td>{'✓' if a.is_intended else ''}</td></tr>"
            for a in c.outcome_top
        )
        parts.append(
            f"<table><tr><th>allele</th><th>probability</th><th>intended</th></tr>{rows}</table>"
        )
    spec = (
        f"; specificity {c.offtarget_specificity:.3f}"
        if c.offtarget_specificity is not None
        else ""
    )
    if c.offtarget_by_ancestry:
        rows = "".join(
            f"<tr><td>{_esc(r.ancestry)}</td><td>{r.worst_score:.3f}</td></tr>"
            for r in c.offtarget_by_ancestry
        )
        parts.append(
            f"<p class='muted'>{c.n_offtarget_sites} nominated site(s){spec}; "
            "worst-case score by ancestry:</p>"
            "<table><tr><th>ancestry</th><th>worst off-target score</th></tr>"
            f"{rows}</table>"
        )
    elif c.n_offtarget_sites is not None:
        parts.append(f"<p class='muted'>{c.n_offtarget_sites} nominated site(s){spec}.</p>")
    if c.flags:
        parts.append("<p class='muted'>flags: " + _esc(", ".join(c.flags)) + "</p>")
    if c.oligos is not None:
        parts.append(
            "<details><summary>Cloning oligos</summary><pre class='mono'>"
            + _esc(c.oligos.model_dump_json(indent=2))
            + "</pre></details>"
        )
    if c.rationale:
        parts.append(f"<p class='muted'>{_esc(c.rationale)}</p>")
    parts.append("</div>")
    return "".join(parts)


def _figure_script(div_id: str, figure: dict[str, Any] | None) -> str:
    """Return a div + Plotly.newPlot script for a figure (empty if no figure)."""
    if figure is None:
        return ""
    spec = json.dumps(figure).replace("</", "<\\/")  # never break out of <script>
    return (
        f"<div id='{div_id}' class='chart'></div>"
        f"<script>var f={spec};Plotly.newPlot('{div_id}',f.data,f.layout,"
        "{responsive:true,displaylogo:false});</script>"
    )


def _provenance_html(report: DesignReport) -> str:
    """Render the provenance footer."""
    p = report.provenance
    if p is None:
        return "<footer>No provenance recorded.</footer>"
    lines = [
        f"AlleleForge {_esc(p.alleleforge_version)}",
        f"reference build {_esc(p.reference_build)}",
        f"seed {_esc(p.seed)}",
        f"generated {_esc(p.timestamp.isoformat())}",
    ]
    if p.models:
        models = ", ".join(f"{_esc(m.name)} {_esc(m.version)}" for m in p.models)
        lines.append(f"models: {models}")
    return "<footer><strong>Provenance.</strong> " + " · ".join(lines) + "</footer>"


def render_html(report: DesignReport) -> str:
    """Render a :class:`DesignReport` as a complete, self-contained HTML string.

    Args:
        report: The report to render.

    Returns:
        A full HTML document (disclaimer first, provenance last) with inlined
        interactive Plotly charts and ancestry-stratified off-target tables.
    """
    variant = _esc(report.variant) if report.variant else "(unspecified)"
    intent = _esc(report.intent) if report.intent else "(default)"
    weights = ", ".join(f"{k} {v:.2f}" for k, v in report.weights.items()) or "default"
    body = [
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>{_esc(report.title)}</title>",
        f"<script src='{PLOTLY_CDN}'></script>",
        f"<style>{_STYLE}</style></head><body>",
        f"<header><h1>{_esc(report.title)}</h1>",
        f"<p class='muted'>variant <span class='mono'>{variant}</span> · "
        f"intent {intent} · ranking weights: {_esc(weights)}</p></header>",
        f"<div class='disclaimer'><strong>Research use only.</strong> "
        f"{_esc(report.disclaimer)}</div>",
        _figure_script("eff-chart", _efficiency_figure(report)),
        _figure_script("ot-chart", _offtarget_figure(report)),
        "<h2>Candidates</h2>",
    ]
    if report.candidates:
        body.extend(_candidate_html(c) for c in report.candidates)
    else:
        body.append("<p class='muted'>No candidates were produced for this variant.</p>")
    body.append(
        "<p class='muted'>Genomic context: load the candidate loci in a "
        "<a href='https://jbrowse.org/jb2/'>JBrowse 2</a> instance for an "
        "interactive browser view (optional).</p>"
    )
    body.append(_provenance_html(report))
    body.append("</body></html>")
    return "".join(body)
