"""Render a design report as a self-contained, interactive HTML page.

The HTML leads with the research-use disclaimer and ends with provenance, as the
spec requires. Off-target tables are ancestry-stratified.

Charts are **inlined SVG**, drawn by AlleleForge's own dependency-free renderer
(:mod:`alleleforge.viz.svg`). They used to be interactive Plotly figures with the
library pulled from ``cdn.plot.ly`` — a decision this docstring defended as "a static
script, never sequence data", and which was wrong in a way the docstring could not see:
the README, the deployment guide and the served page all promise "no outbound network
call" and "the served frontend loads no third-party scripts", and a lab opening the
local UI to analyse a patient variant was issuing a request to a CDN at that moment.
The request itself is the disclosure, whatever it carries. It also ran third-party
script in an unsandboxed same-origin iframe.

Nothing in a rendered report reaches the network: the page is one self-contained file,
data and charts alike.
"""

from __future__ import annotations

import html
from collections.abc import Sequence

from alleleforge.report.builder import (
    DEFAULT_RENDER_CANDIDATES,
    NOMINATED_SITES_NOTE,
    VARIANT_POSITION_NOTE,
    WITHHELD_ALLELES_NOTE,
    WITHHELD_CANDIDATES_NOTE,
    CandidateReport,
    DesignReport,
    caveats,
    model_limitation_lines,
    provenance_lines,
    uncovered_prediction_notes,
    visible_candidates,
)
from alleleforge.report.pdf import oligo_lines
from alleleforge.types.prediction import Prediction
from alleleforge.viz.svg import Series, bar_chart

#: This report is a fixed light document: a cream disclaimer panel, teal headings, and
#: inlined SVG charts that paint their own white ground. It set `color: #1a1a1a` and no
#: background, so `body` took the user agent's — and in a browser set to dark the whole
#: page rendered as near-black text on a dark ground, i.e. blank. It is the artifact a
#: collaborator is *sent*, opened on a machine whose theme the author never sees, so it
#: declares the scheme it was drawn for rather than inheriting the reader's.
#:
#: Series colors for the grouped off-target chart, cycled per candidate. Fixed and
#: ordered so a re-render of the same report is byte-identical.
_SERIES_COLORS: tuple[str, ...] = ("#0a7d77", "#b45309", "#4f46e5", "#be123c", "#0369a1")

_STYLE = """
:root { color-scheme: light;
        --paper:#ffffff; --teal:#0a7d77; --ink:#1a1a1a; --muted:#666; --line:#e2e2e2; }
* { box-sizing: border-box; }
body { font-family: -apple-system, Segoe UI, Roboto, sans-serif;
       background: var(--paper); color: var(--ink);
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
/* A `<pre>` defaults to `white-space: pre` with no overflow rule, so the rationale — one
   long line per routing decision — laid out 5,903px wide inside a 1,217px column and
   pushed the *document* to scroll sideways, dragging the disclaimer, the charts and every
   candidate off-screen with it. The rationale is prose and wraps. The oligo block is DNA:
   a spacer broken across two lines is a spacer someone mis-copies into an order form, so
   it keeps its line and scrolls inside its own box. Neither may move the page. */
pre { max-width: 100%; overflow-x: auto; }
.rationale-block { white-space: pre-wrap; overflow-wrap: anywhere; }
table { border-collapse: collapse; margin:0.5rem 0; font-size:0.88rem; }
th, td { border:1px solid var(--line); padding:0.3rem 0.6rem; text-align:left; }
th { background:#f4f9f8; }
.muted { color: var(--muted); font-size:0.85rem; }
/* A hazard is not a footnote. Caveats and ordering warnings were `.muted` — smaller
   and greyer than body text, in the same class as "showing 3 of 54 alleles" and the
   ligation prep reminder — so "the enzyme that assembles this cuts the insert" was
   typeset as de-emphasis. Full size, full ink, and the same amber the research-use
   panel at the top of the page uses, which is this report's existing warning colour. */
.hazard { background:#fff8e6; border-left:3px solid #e8c96b; border-radius:0 4px 4px 0;
          padding:0.4rem 0.7rem; margin:0.5rem 0; font-size:0.95rem; color: var(--ink); }
/* The responsive rule was written for the wrapper and never reached the picture. An
   inlined SVG carries its own `width="720" height="380"`, which wins: the box was 320px
   tall around a 380px drawing (60px of chart painted over the heading below it), and the
   720px width could not shrink, so any viewport under ~770px scrolled sideways to see a
   figure that had a `viewBox` and could have scaled all along. Styling the element, not
   the box, and letting the aspect ratio come from the viewBox. */
.chart { width:100%; max-width:760px; }
.chart svg { display:block; width:100%; height:auto; }
footer { margin-top:2rem; border-top:1px solid var(--line); padding-top:1rem;
         font-size:0.8rem; color: var(--muted); }
/* Paper has no affordances. A scroll box scrolls on screen and is simply cut off by a
   printer: measured at a 624px print column, the cloning-oligo block is 876px of
   sequence in a 536px box, so 340px of it — the tail of every duplex — does not print.
   That is the third way this report has managed to hand someone a truncated sequence,
   after the PDF's right margin and its page breaks, and the same order goes wrong.
   Sequences therefore wrap on paper, where wrapping is recoverable and clipping is not.
   Backgrounds are dropped by default when printing, which would erase the panels that
   separate a cloning-lethal warning from a footnote — the whole point of that styling —
   so the two that carry meaning are marked to print. And a candidate, a figure or a
   table split across a sheet is a reagent read half on each. */
@media print {
  pre { white-space: pre-wrap; overflow-wrap: anywhere; overflow: visible; }
  .candidate, .chart, table, details { break-inside: avoid; }
  .hazard, .disclaimer { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
""".strip()


def _esc(text: object) -> str:
    """HTML-escape any value's string form."""
    return html.escape(str(text))


def _efficiency_figure(report: DesignReport) -> str:
    """Render efficiency per candidate as an inlined SVG bar chart.

    The interval is drawn as a reference band rather than Plotly error bars: the SVG
    renderer has no error-bar primitive, and the interval is already printed beside
    every candidate, so the chart carries the comparison and the text carries the
    numbers. Returns "" when no candidate has an efficiency to plot.
    """
    categories: list[str] = []
    values: list[float] = []
    plotted: list[Prediction[float]] = []
    for c in report.candidates:
        if c.efficiency is None:
            continue
        categories.append(f"#{c.rank} {c.chemistry.value}")
        values.append(round(c.efficiency.value, 4))
        plotted.append(c.efficiency)
    if not categories:
        return ""
    return bar_chart(
        title=_efficiency_title(plotted),
        subtitle=_efficiency_subtitle(plotted),
        categories=tuple(categories),
        series=(Series(name="efficiency", values=tuple(values), color="#0a7d77"),),
        y_label="efficiency",
        y_max=1.0,
    )


def _quantify(n: int, total: int, claim: str) -> str:
    """Return ``claim`` scoped to how many of ``total`` bars it is true of."""
    if n == 0:
        return ""
    return claim if n == total else f"{n} of {total} bars: {claim}"


def _efficiency_title(plotted: Sequence[Prediction[float]]) -> str:
    """Return a chart title that does not claim more than the bars support.

    The title was the fixed string "Calibrated efficiency". Every candidate underneath
    it printed "(nominal — coverage not measured)" and "(heuristic point estimate — not
    from a trained model)", because with the bundled models nothing on the page is
    calibrated and nothing came from a trained model. The chart is the first thing a
    reader looks at, and it asserted the opposite of every line below it — an honesty
    mechanism that reached the text and stopped at the figure.
    """
    return "Calibrated efficiency" if all(p.calibrated for p in plotted) else "Predicted efficiency"


def _efficiency_subtitle(plotted: Sequence[Prediction[float]]) -> str:
    """Return the chart subtitle, naming what the bars are and are not."""
    total = len(plotted)
    notes = [
        "point estimate; the 80% interval is printed beside each candidate",
        _quantify(
            sum(1 for p in plotted if not p.calibrated),
            total,
            "intervals are nominal, coverage not measured",
        ),
        _quantify(
            sum(1 for p in plotted if not p.point_from_trained_model),
            total,
            "heuristic point estimates, not from a trained model",
        ),
        _quantify(
            sum(1 for p in plotted if not p.in_distribution),
            total,
            "out-of-distribution",
        ),
    ]
    return "; ".join(n for n in notes if n)


def _offtarget_figure(report: DesignReport) -> str:
    """Render worst-case off-target score per ancestry as an inlined SVG bar chart.

    One series per candidate, grouped by ancestry. Returns "" when no candidate
    carries an ancestry breakdown.
    """
    ancestries: list[str] = []
    for c in report.candidates:
        for row in c.offtarget_by_ancestry:
            if row.ancestry not in ancestries:
                ancestries.append(row.ancestry)
    if not ancestries:
        return ""
    series: list[Series] = []
    for i, c in enumerate(report.candidates):
        # A candidate that was never off-target-searched has no worst-case score;
        # drawing it as 0.0 would paint "risk unknown" as the safest possible bar and
        # could flip a visual ranking toward the least-evidenced guide. A *searched*
        # candidate with no sites (n == 0) legitimately plots 0.0 — only skip None.
        if c.n_offtarget_sites is None:
            continue
        by = {r.ancestry: r.worst_score for r in c.offtarget_by_ancestry}
        series.append(
            Series(
                name=f"#{c.rank} {c.chemistry.value}",
                values=tuple(round(by.get(a, 0.0), 4) for a in ancestries),
                color=_SERIES_COLORS[i % len(_SERIES_COLORS)],
            )
        )
    if not series:
        return ""
    return bar_chart(
        title="Worst-case off-target score by ancestry",
        categories=tuple(ancestries),
        series=tuple(series),
        y_label="off-target score",
        y_max=1.0,
    )


def _untrained(prediction: Prediction[float]) -> str:
    """Say when a point estimate did not come from a trained model.

    `calibrated=False` qualifies the *interval*; nothing qualified the *point*. The
    bundled Cas9 ensemble's model card carries this as its load-bearing sentence — "the
    heads are an unfitted pseudo-random scaffold: the point estimate is not a trained
    activity prediction" — and `point_from_trained_model` records it per prediction. It
    reached no human surface, so a report printed `Efficiency 0.60` in exactly the
    typography a trained model's estimate would get.
    """
    if prediction.point_from_trained_model:
        return ""
    return f" <em>({prediction.method.value} point estimate — not from a trained model)</em>"


def _candidate_html(c: CandidateReport) -> str:
    """Render one candidate block."""
    badge = '<span class="badge">Pareto</span>' if c.on_pareto_front else ""
    parts = [f"<div class='candidate'><h3>#{c.rank} · {_esc(c.chemistry.value)}{badge}</h3>"]
    parts.append(f"<div class='mono'>{_esc(c.reagent)}</div>")
    # The contig-qualified locus, beside the reagent it belongs to. Without it the
    # page named no chromosome anywhere, while the provenance block below described
    # the coordinate convention those absent coordinates were in.
    if c.locus is not None:
        parts.append(f"<div class='mono'>{_esc(c.locus)}</div>")
    if c.efficiency is not None:
        e = c.efficiency
        ood = "" if e.in_distribution else " <strong>(out-of-distribution)</strong>"
        cal = "" if e.calibrated else " <em>(nominal — coverage not measured)</em>"
        parts.append(
            f"<p>Efficiency <strong>{e.value:.2f}</strong> "
            f"[{e.interval[0]:.2f}, {e.interval[1]:.2f}] @ {e.interval_level:.0%}"
            f"{cal}{_untrained(e)}{ood}</p>"
        )
    if c.bystander_burden is not None:
        b = c.bystander_burden
        cal = "" if b.calibrated else " <em>(nominal — coverage not measured)</em>"
        parts.append(
            f"<p>Bystander burden <strong>{b.value:.2f}</strong> "
            f"[{b.interval[0]:.2f}, {b.interval[1]:.2f}] @ {b.interval_level:.0%}{cal}</p>"
        )
    for note in uncovered_prediction_notes(c):
        parts.append(f"<p class='muted'><strong>note:</strong> {_esc(note)}</p>")
    if c.p_intended is not None:
        # The number a reader is most likely to act on. Where the chemistry's outcome
        # predictor made a prediction for it, it carries the same envelope efficiency
        # and bystander burden do; where it did not (SpCas9), the figure is a derived
        # sum over the indel spectrum and says so rather than being shown as if it
        # were of the same kind.
        prediction = c.p_intended_prediction
        if prediction is None:
            parts.append(
                f"<p>P(intended) = <strong>{c.p_intended:.2f}</strong> "
                "<em>(derived from the outcome distribution; no calibrated "
                "interval)</em></p>"
            )
        else:
            cal = "" if prediction.calibrated else " <em>(nominal — coverage not measured)</em>"
            ood = "" if prediction.in_distribution else " <em>(out of distribution)</em>"
            parts.append(
                f"<p>P(intended) = <strong>{prediction.value:.2f}</strong> "
                f"[{prediction.interval[0]:.2f}, {prediction.interval[1]:.2f}] "
                f"@ {prediction.interval_level:.0%}{cal}{_untrained(prediction)}{ood}</p>"
            )
    if c.outcome_top:
        rows = "".join(
            f"<tr><td class='mono'>{_esc(a.allele)}</td><td>{a.probability:.3f}</td>"
            f"<td>{'✓' if a.is_intended else ''}</td></tr>"
            for a in c.outcome_top
        )
        parts.append(
            f"<table><tr><th>allele</th><th>probability</th><th>intended</th></tr>{rows}</table>"
        )
        if c.n_outcome_alleles > len(c.outcome_top):
            parts.append(
                f"<p class='muted'>showing {len(c.outcome_top)} of {c.n_outcome_alleles} "
                f"predicted alleles ({c.outcome_shown_mass:.2f} of the probability mass); "
                f"{_esc(WITHHELD_ALLELES_NOTE)}.</p>"
            )
    spec = (
        f"; specificity {c.offtarget_specificity:.3f}"
        if c.offtarget_specificity is not None
        else ""
    )
    # Only when some site's presence is probabilistic: with reference sites alone this
    # is the unweighted score sum and adds a number without adding a fact.
    if c.offtarget_expected_burden is not None:
        spec += f"; expected burden {c.offtarget_expected_burden:.3f} (frequency-weighted)"
    # Which matrix produced the worst score, when the table mixes two.
    if c.offtarget_worst_matrix is not None:
        spec += f"; worst site scored by {_esc(c.offtarget_worst_matrix)}"

    if c.offtarget_by_ancestry:
        rows = "".join(
            f"<tr><td>{_esc(r.ancestry)}</td><td>{r.worst_score:.3f}</td>"
            f"<td>{r.expected_burden:.4f}</td></tr>"
            for r in c.offtarget_by_ancestry
        )
        # Both columns. A score does not depend on ancestry, so the worst-case column
        # reads the same for every stratum on exactly the finding this engine exists to
        # reproduce, while the carrying frequency spans a hundredfold.
        parts.append(
            f"<p class='muted'>{c.n_offtarget_sites} nominated site(s){spec}; "
            "by ancestry — the worst-case score, and how often a genome from that "
            "population carries it:</p>"
            "<table><tr><th>ancestry</th><th>worst off-target score</th>"
            "<th>expected burden</th></tr>"
            f"{rows}</table>"
        )
    elif c.n_offtarget_sites is not None:
        parts.append(f"<p class='muted'>{c.n_offtarget_sites} nominated site(s){spec}.</p>")
    if c.n_offtarget_sites:
        # Only when there are sites: with none nominated there is nothing to go and read.
        parts.append(f"<p class='muted'>{_esc(NOMINATED_SITES_NOTE)}.</p>")
    if c.n_offtarget_sites is not None and (c.offtarget_scorer or c.offtarget_matrix):
        basis = " / ".join(p for p in (c.offtarget_scorer, c.offtarget_matrix) if p)
        # The published method, on the same line as the scorer's name: a reader
        # checking whose CFD this is should not have to open the source to find out.
        cite = f" — {c.offtarget_scorer_citation}" if c.offtarget_scorer_citation else ""
        parts.append(f"<p class='muted'>off-target scoring basis: {_esc(basis)}{_esc(cite)}.</p>")
    if c.offtarget_search is not None:
        parts.append(f"<p class='muted'>off-target search: {_esc(c.offtarget_search)}.</p>")
    # Hazards first and on their own, before the flat flag list: a `close-nick` printed
    # inside a comma-separated line reads with the same weight as `epegRNA:tevopreQ1`.
    for flag, reason in caveats(c.flags):
        parts.append(
            f"<p class='hazard'><strong>caveat &mdash; {_esc(flag)}:</strong> {_esc(reason)}</p>"
        )
    if c.flags:
        parts.append("<p class='muted'>flags: " + _esc(", ".join(c.flags)) + "</p>")
    if c.oligos is not None:
        for warning in c.oligos.warnings:
            parts.append(f"<p class='hazard'><strong>oligo warning:</strong> {_esc(warning)}</p>")
        if c.oligos.scheme.phosphorylation:
            parts.append(
                "<p class='muted'><strong>oligo prep:</strong> "
                + _esc(c.oligos.scheme.phosphorylation)
                + "</p>"
            )
        # The same lines the printable sheet builds, not a JSON dump of the record.
        # The dump technically "contained" everything — which is how the HDR donor and
        # the prepended-G note counted as rendered here while being absent from the
        # sheet a lab actually orders from — but a reader scanning a report does not
        # read a serialized object, and the two surfaces then drift by construction.
        block = "\n".join(line.strip() for line in oligo_lines(c.oligos) if line.strip())
        parts.append(
            "<details><summary>Cloning oligos</summary><pre class='mono'>"
            + _esc(block)
            + "</pre></details>"
        )
    elif c.oligos_requested:
        parts.append("<p class='muted'>Cloning oligos: none required (no synthesized reagent).</p>")
    if c.rationale:
        parts.append(f"<p class='muted'>{_esc(c.rationale)}</p>")
    parts.append("</div>")
    return "".join(parts)


def _figure_block(div_id: str, svg: str) -> str:
    """Wrap an inlined SVG chart in its container (empty string when there is none).

    The SVG is produced entirely by `alleleforge.viz.svg`, which escapes every label
    it draws and validates every color, so no user-supplied ancestry or chemistry
    string can break out of it — and unlike the JSON-in-`<script>` this replaced,
    there is no script element for it to break out *into*.
    """
    if not svg:
        return ""
    return f"<div id='{div_id}' class='chart'>{svg}</div>"


def _provenance_html(report: DesignReport) -> str:
    """Render the provenance footer."""
    if report.provenance is None:
        return "<footer>No provenance recorded.</footer>"
    lines = [_esc(line) for line in provenance_lines(report.provenance)]
    footer = "<footer><strong>Provenance.</strong> " + " · ".join(lines) + "</footer>"
    limits = model_limitation_lines(report.provenance)
    if limits:
        items = "".join(f"<li>{_esc(line)}</li>" for line in limits)
        footer += (
            "<footer><strong>Model limitations.</strong> What the model cards say these "
            f"models are not for, and how they fail.<ul>{items}</ul></footer>"
        )
    return footer


def _unavailable_html(report: DesignReport) -> str:
    """Render the chemistries that contributed nothing for a non-biological reason.

    Above the rationale and not inside it: a defect in this tool, or a store whose
    integrity check failed, is not one of the routing verdicts a reader skims — it is the
    reason part of this menu is missing, and the reader has to see it without opening a
    disclosure widget.
    """
    if not report.unavailable:
        return ""
    items = "".join(f"<li>{_esc(note)}</li>" for note in report.unavailable)
    return (
        f"<div class='hazard'><strong>Part of this menu is missing.</strong><ul>{items}</ul></div>"
    )


def _run_notes_html(report: DesignReport) -> str:
    """Render what a caller can act on about the run, above the rationale.

    Beside `_unavailable_html` and for the same reason: a population source built for
    another assembly is why the ancestry columns are empty, not one of the routing
    verdicts a reader skims — and inside a candidate's search paragraph, repeated once
    per reagent, it is present and not seen.
    """
    if not report.notes:
        return ""
    items = "".join(f"<li>{_esc(note)}</li>" for note in report.notes)
    return (
        "<div class='hazard'><strong>About this run, not about a candidate.</strong>"
        f"<ul>{items}</ul></div>"
    )


def _rationale_html(report: DesignReport) -> str:
    """Render the menu-level rationale (routing verdicts, skips, failures).

    An empty report with no explanation is the worst artifact this renderer can
    produce, and it is exactly what a mistyped option yields: the designer degrades
    gracefully, records the reason, and every renderer used to drop it.
    """
    if not report.rationale:
        return ""
    return (
        "<details open><summary>How this menu was assembled</summary>"
        f"<pre class='mono rationale-block'>{_esc(report.rationale)}</pre></details>"
    )


def render_html(
    report: DesignReport, *, max_candidates: int | None = DEFAULT_RENDER_CANDIDATES
) -> str:
    """Render a :class:`DesignReport` as a complete, self-contained HTML string.

    Args:
        report: The report to render.
        max_candidates: How many ranked candidates to render, or ``None`` for all.
            Every Pareto-front candidate is rendered whatever the cap, and any
            withheld count is stated on the page. No export is capped: every
            candidate is in the JSON, TSV and Parquet forms whatever this is set to.

    Returns:
        A full, self-contained HTML document (disclaimer first, provenance last)
        with inlined SVG charts and ancestry-stratified off-target tables. It
        references nothing off-origin, so opening it issues no network request.
    """
    variant = _esc(report.variant) if report.variant else "(unspecified)"
    intent = _esc(report.intent) if report.intent else "(default)"
    weights = ", ".join(f"{k} {v:.2f}" for k, v in report.weights.items()) or "default"
    body = [
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>{_esc(report.title)}</title>",
        f"<style>{_STYLE}</style></head><body>",
        f"<header><h1>{_esc(report.title)}</h1>",
        f"<p class='muted'>variant <span class='mono'>{variant}</span> · "
        f"intent {intent} · ranking weights: {_esc(weights)}</p>",
        # Beside the variant, not in the footer: a reader who typed a 1-based position
        # and reads a number one lower here needs the explanation where the surprise is.
        (
            f"<p class='muted'>{_esc(VARIANT_POSITION_NOTE)}.</p></header>"
            if report.variant
            else "</header>"
        ),
        f"<div class='disclaimer'><strong>Research use only.</strong> "
        f"{_esc(report.disclaimer)}</div>",
        _unavailable_html(report),
        _run_notes_html(report),
        _rationale_html(report),
        _figure_block("eff-chart", _efficiency_figure(report)),
        _figure_block("ot-chart", _offtarget_figure(report)),
        "<h2>Candidates</h2>",
    ]
    shown, withheld = visible_candidates(report, max_candidates)
    if withheld:
        body.append(
            f"<p class='muted'>Showing {len(shown)} of {len(report.candidates)} candidates: "
            f"the top {max_candidates} by rank plus every Pareto-front candidate. "
            f"The remaining {withheld} are not lost: {WITHHELD_CANDIDATES_NOTE}.</p>"
        )
    if shown:
        body.extend(_candidate_html(c) for c in shown)
    else:
        body.append("<p class='muted'>No candidates were produced for this variant.</p>")
    body.append(
        "<p class='muted'>Genomic context: load the candidate loci in a "
        "<a href='https://jbrowse.org/jb2/' target='_blank' "
        "rel='noopener noreferrer'>JBrowse 2</a> instance for an "
        "interactive browser view (optional).</p>"
    )
    body.append(_provenance_html(report))
    body.append("</body></html>")
    return "".join(body)
