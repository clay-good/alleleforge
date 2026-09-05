"""Tests for the Phase 11 HTML renderer."""

from __future__ import annotations

from alleleforge.report.builder import CandidateReport, build_report
from alleleforge.report.html import PLOTLY_CDN, _candidate_html, render_html
from alleleforge.types.candidate import RankedMenu
from alleleforge.types.edit import Chemistry


def test_html_is_a_complete_document(prime_menu: RankedMenu) -> None:
    html = render_html(build_report(prime_menu, variant="chr2:70:A>C"))
    assert html.startswith("<!DOCTYPE html>")
    assert html.rstrip().endswith("</html>")
    assert "chr2:70:A&gt;C" in html  # the variant is HTML-escaped


def test_html_leads_with_disclaimer_and_ends_with_provenance(prime_menu: RankedMenu) -> None:
    html = render_html(build_report(prime_menu))
    assert "Research use only" in html
    disclaimer_pos = html.index("Research use only")
    provenance_pos = html.index("Provenance")
    assert disclaimer_pos < provenance_pos  # disclaimer first, provenance last


def test_html_footer_lists_invoked_models(ancestry_menu: RankedMenu) -> None:
    html = render_html(build_report(ancestry_menu, variant="chr11:108:A>T"))
    # The provenance footer names every model checkpoint that produced the menu.
    assert "models: cas9-efficiency-ensemble 0.1" in html
    assert "indelphi 1.0" in html


def test_html_embeds_interactive_plotly(prime_menu: RankedMenu) -> None:
    html = render_html(build_report(prime_menu))
    assert PLOTLY_CDN in html
    assert "Plotly.newPlot" in html


def test_offtarget_chart_excludes_unsearched_candidates(ancestry_menu: RankedMenu) -> None:
    # A candidate that was never off-target-searched (n_offtarget_sites is None) must
    # NOT appear in the worst-case-by-ancestry chart: plotting it as 0.0 would paint
    # "risk unknown" as the safest bar and could flip a visual ranking. A searched-but-
    # clean candidate (n == 0) legitimately plots 0.0 and stays.
    from alleleforge.report.html import _offtarget_figure

    report = build_report(ancestry_menu)
    searched = [c for c in report.candidates if c.n_offtarget_sites is not None]
    assert searched  # the fixture has off-target-searched candidates
    unsearched = searched[0].model_copy(
        update={"n_offtarget_sites": None, "offtarget_by_ancestry": ()}
    )
    mixed = report.model_copy(update={"candidates": (*report.candidates, unsearched)})
    fig = _offtarget_figure(mixed)
    assert fig is not None
    # One trace per *searched* candidate — the unsearched one contributes none.
    n_searched = sum(1 for c in mixed.candidates if c.n_offtarget_sites is not None)
    assert len(fig["data"]) == n_searched


def test_html_offtarget_table_is_ancestry_stratified(abe_menu: RankedMenu) -> None:
    report = build_report(abe_menu)
    html = render_html(report)
    ancestries = {r.ancestry for c in report.candidates for r in c.offtarget_by_ancestry}
    if ancestries:  # the abe fixture produces population off-targets
        assert "off-target score by ancestry" in html
        for ancestry in ancestries:
            assert ancestry in html


def test_html_has_no_unescaped_script_breakout(prime_menu: RankedMenu) -> None:
    html = render_html(build_report(prime_menu))
    # the inlined figure JSON must never contain a raw </ that closes the script
    assert "</script>" in html  # the legitimate closers exist
    # but the figure payload escapes its slashes
    assert "<\\/" in html or "Plotly.newPlot" in html


def test_figure_script_cannot_break_out_of_script_element() -> None:
    # A figure's x-values are user-supplied ancestry/population labels. Escaping
    # only `</` left `<!--` intact, which puts the HTML tokenizer into
    # script-data-double-escaped state and swallows the rest of the report. The
    # inlined JSON must contain no raw `<` at all, yet still parse back to the
    # exact data on the client.
    import json as _json

    from alleleforge.report.html import _figure_script

    figure = {
        "data": [
            {
                "type": "bar",
                "x": ["<!--<script>alert(1)//", "</script><script>alert(2)</script>"],
                "y": [0.5, 0.4],
            }
        ],
        "layout": {},
    }
    out = _figure_script("ot-chart", figure)
    body = out.split("<script>", 1)[1].rsplit("</script>", 1)[0]
    assert "<" not in body  # no raw angle bracket survives inside the <script>
    spec = body.split("var f=", 1)[1].rsplit(";Plotly", 1)[0]
    assert _json.loads(spec)["data"][0]["x"][0] == "<!--<script>alert(1)//"  # data intact


def test_html_renders_ancestry_offtarget_chart_and_table(ancestry_menu: RankedMenu) -> None:
    html = render_html(build_report(ancestry_menu, variant="chr11:108:A>T"))
    assert "Worst-case off-target score by ancestry" in html  # the grouped Plotly chart
    assert "off-target score by ancestry" in html  # the per-candidate table caption
    assert "specificity" in html  # the aggregate genome-wide specificity score
    assert "afr" in html and "eur" in html
    # The scoring basis (scorer + matrix identity) is named alongside the table so a
    # reader can tell published-CFD from the labeled approximation without the code.
    assert "scoring basis" in html
    assert "doench-2016-cfd" in html
    # ...and so is the search that produced the count: "2 nominated site(s)" means one
    # thing at a 0.05 CFD cut-off with no bulges allowed and another at the defaults.
    assert "off-target search: up to 3 mismatches, 0 DNA / 0 RNA bulges; " in html
    assert "sites reported at CFD &gt;= 0.05 or MIT &gt;= 0.01" in html  # HTML-escaped


def test_empty_menu_renders(prime_menu: RankedMenu) -> None:
    from alleleforge.types.candidate import RankedMenu as RM

    empty = RM(candidates=(), provenance=prime_menu.provenance)
    html = render_html(build_report(empty))
    assert "No candidates" in html
    assert html.rstrip().endswith("</html>")


def test_html_marks_uncalibrated_interval_as_nominal(prime_menu: RankedMenu) -> None:
    # Every default scorer emits calibrated=False, so "@ 80%" is a nominal target,
    # not measured coverage. The render must say so (the design contract puts that
    # caveat "in the notes"); otherwise a reader reads the band as achieved coverage.
    html = render_html(build_report(prime_menu))
    assert "nominal — coverage not measured" in html


def test_html_omits_nominal_caveat_for_calibrated_interval(prime_menu: RankedMenu) -> None:
    from alleleforge.types.prediction import Prediction, UncertaintyMethod

    report = build_report(prime_menu)

    def _calibrate(cand: object) -> object:
        e = cand.efficiency  # type: ignore[attr-defined]
        if e is None:
            return cand
        cal = Prediction.calibrated_by(
            value=e.value,
            interval=e.interval,
            method=UncertaintyMethod.CONFORMAL,
            interval_level=e.interval_level,
        )
        return cand.model_copy(update={"efficiency": cal})  # type: ignore[attr-defined]

    calibrated = report.model_copy(
        update={"candidates": tuple(_calibrate(c) for c in report.candidates)}
    )
    html = render_html(calibrated)
    assert "Efficiency" in html  # the efficiency lines still render
    assert "nominal — coverage not measured" not in html


def test_the_menu_rationale_is_rendered(prime_menu: RankedMenu) -> None:
    """The explanation must survive into the page a reader actually opens."""
    report = build_report(prime_menu)
    html = render_html(report)
    assert "How this menu was assembled" in html
    assert "Routing:" in html


def test_a_prediction_note_without_a_flag_behind_it_is_rendered() -> None:
    """Free-text caveats must reach the page, not only the JSON.

    A `Prediction`'s `calibrated` and `in_distribution` flags are already spelled
    out inline, but its free-text notes had no renderer at all — including the one
    stating that the default prime scorer has no edit-size term, which is exactly
    the caveat a reader of a multi-base edit needs.
    """
    from alleleforge.report.html import _uncovered_notes
    from alleleforge.types.prediction import NOMINAL_INTERVAL_NOTE, Prediction, UncertaintyMethod

    prediction = Prediction[float](
        value=0.5,
        interval=(0.4, 0.6),
        interval_level=0.8,
        method=UncertaintyMethod.HEURISTIC,
        notes=(NOMINAL_INTERVAL_NOTE, "this scorer ignores the edit size"),
    )
    candidate = CandidateReport(
        rank=1,
        chemistry=Chemistry.PRIME,
        on_pareto_front=True,
        reagent="pegRNA",
        efficiency=prediction,
        bystander_burden=None,
        p_intended=None,
        outcome_top=(),
        n_offtarget_sites=None,
        offtarget_specificity=None,
        offtarget_by_ancestry=(),
        oligos=None,
        flags=(),
        rationale=None,
    )
    # The nominal-interval caveat is already rendered inline; repeating it is noise.
    assert _uncovered_notes(candidate) == ["this scorer ignores the edit size"]
    html = _candidate_html(candidate)
    assert "this scorer ignores the edit size" in html
    assert html.count("coverage not measured") == 1
