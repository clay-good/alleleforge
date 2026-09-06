"""Tests for the Phase 11 HTML renderer."""

from __future__ import annotations

from alleleforge.report.builder import CandidateReport, build_report
from alleleforge.report.html import _candidate_html, render_html
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


def test_html_embeds_its_charts_inline(prime_menu: RankedMenu) -> None:
    """This test used to assert the opposite: that the page loaded Plotly from a CDN.

    Two tests asserted contradictory things — this one that the report pulls a
    third-party script, and the frontend guard that nothing off-origin is loaded —
    and both passed, because the guard scanned the static asset directory and the
    report is generated. The chart is now inlined SVG from `alleleforge.viz.svg`.
    """
    html = render_html(build_report(prime_menu))
    assert "<svg" in html
    assert "Calibrated efficiency" in html
    assert "cdn.plot.ly" not in html


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
    before = _offtarget_figure(report)
    after = _offtarget_figure(mixed)
    assert before, "the fixture must produce a chart for this check to mean anything"
    # The property, independent of how the chart is drawn: an unsearched candidate
    # contributes nothing at all, so adding one leaves the figure byte-identical.
    assert after == before


def test_html_offtarget_table_is_ancestry_stratified(abe_menu: RankedMenu) -> None:
    report = build_report(abe_menu)
    html = render_html(report)
    ancestries = {r.ancestry for c in report.candidates for r in c.offtarget_by_ancestry}
    if ancestries:  # the abe fixture produces population off-targets
        assert "off-target score by ancestry" in html
        for ancestry in ancestries:
            assert ancestry in html


def test_the_report_contains_no_script_element_at_all(prime_menu: RankedMenu) -> None:
    """The strongest form of the escaping property: there is nothing to break out of.

    This replaced two tests that checked the inlined figure JSON could not escape its
    `<script>` element — careful work against a real class of bug (a user-supplied
    ancestry label putting the tokenizer into script-data-double-escaped state). The
    charts are inlined SVG now, so the script element is gone, and with it the whole
    injection surface those tests were defending.
    """
    html = render_html(build_report(prime_menu))
    assert "<script" not in html


def test_a_hostile_ancestry_label_cannot_break_out_of_the_chart() -> None:
    """A chart's category labels are user-supplied population strings.

    The old defence escaped JSON for a `<script>` context. The new one is that
    `alleleforge.viz.svg` escapes every label it draws, so the same hostile input has
    to be inert in the SVG — which is where it now lands.
    """
    from alleleforge.viz.svg import Series, bar_chart

    hostile = "</text><script>alert(1)</script>"
    svg = bar_chart(
        title="t",
        categories=(hostile, "afr"),
        series=(Series(name="s", values=(0.5, 0.4), color="#0a7d77"),),
    )
    assert "<script>" not in svg
    assert "&lt;" in svg  # the hostile label survives only as escaped text


def test_html_renders_ancestry_offtarget_chart_and_table(ancestry_menu: RankedMenu) -> None:
    html = render_html(build_report(ancestry_menu, variant="chr11:108:A>T"))
    assert "Worst-case off-target score by ancestry" in html  # the grouped SVG chart
    assert "off-target score by ancestry" in html  # the per-candidate table caption
    assert "specificity" in html  # the aggregate genome-wide specificity score
    assert "afr" in html and "eur" in html
    # The scoring basis (scorer + matrix identity) is named alongside the table so a
    # reader can tell published-CFD from the labeled approximation without the code.
    assert "scoring basis" in html
    assert "doench-2016-cfd" in html
    # ...and so is the search that produced the count: "2 nominated site(s)" means one
    # thing at a 0.05 CFD cut-off with no bulges allowed and another at the defaults.
    assert "up to 3 mismatches, 0 DNA / 0 RNA bulges; " in html
    # ...including how much sequence it covered: the scope moves the specificity
    # more than any other setting, and used to go unstated whenever it resolved.
    assert "off-target search: over 248,956,422 bases; " in html
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
        # Calibrate *every* prediction on the candidate, not only efficiency. The
        # caveat is asserted absent from the whole page, so leaving a genuinely
        # uncalibrated neighbour (bystander burden, p_intended) in place would make
        # this test fail for a reason that has nothing to do with what it checks —
        # and it did, the first time `p_intended` grew an interval.
        update = {}
        for field in ("efficiency", "bystander_burden", "p_intended_prediction"):
            prediction = getattr(cand, field, None)
            if prediction is not None:
                update[field] = Prediction.calibrated_by(
                    value=prediction.value,
                    interval=prediction.interval,
                    method=UncertaintyMethod.CONFORMAL,
                    interval_level=prediction.interval_level,
                )
        if not update:
            return cand
        return cand.model_copy(update=update)  # type: ignore[attr-defined]

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


def test_a_rendered_report_fetches_nothing_off_origin(prime_menu: RankedMenu) -> None:
    """The report is part of the page the user sees, and it reached a CDN.

    The README, the deployment guide and the served page all promise "no outbound
    network call" and "the served frontend loads no third-party scripts". The report
    carried `<script src="https://cdn.plot.ly/plotly-2.35.2.min.js">`, which
    `report/html.py`'s own docstring defended as "a static script, never sequence
    data" — but the request itself is the disclosure, whatever it carries, and a lab
    opening the local UI to analyse a patient variant issued it at that moment. It also
    ran third-party script inside an unsandboxed same-origin iframe.

    R151's guard scanned the static asset directory, which this file is not in. Charts
    are inlined SVG from `alleleforge.viz.svg` now, so the page needs no script at all.
    """
    from tests.web.test_frontend_is_self_contained import _LOADERS, _is_off_origin

    page = render_html(build_report(prime_menu))
    offenders = [
        target for pattern in _LOADERS for target in pattern.findall(page) if _is_off_origin(target)
    ]
    assert not offenders, f"the rendered report loads third-party resources: {offenders}"
    assert "<script" not in page, "the report should need no script element at all"
    # ...and it still draws its charts.
    assert "<svg" in page


def test_the_html_shows_the_same_oligo_block_as_the_printable_sheet() -> None:
    """The HTML dumped the oligo record as JSON, and the two surfaces drifted.

    A serialized object "contains" every field, which is how the HDR donor and the
    prepended-G note counted as rendered in the HTML while being absent from the sheet
    a lab actually orders from. A reader scanning a report does not read a serialized
    object. Both surfaces now render the same lines.
    """
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from alleleforge.report.builder import build_report
    from alleleforge.report.oligos import oligos_for
    from alleleforge.types.candidate import RankedMenu as _Menu
    from report.test_oligos import _precise_cas9_candidate  # type: ignore[import-not-found]

    candidate = _precise_cas9_candidate("TTGGCCAA" * 12 + "TTGG")
    oligos = oligos_for(candidate)
    assert oligos is not None and oligos.donor is not None

    report = build_report(_Menu(candidates=(candidate,), pareto_front=(0,)))
    page = render_html(report)

    # Scoped to the oligo block. Asserting against the whole page passed even with the
    # JSON dump restored, because the candidate summary line above it already reads
    # "+ HDR donor 100 nt" — a search that succeeds is not evidence that the thing you
    # are looking for is where you think it is.
    import re as _re

    block = _re.search(r"<details><summary>Cloning oligos</summary>(.*?)</details>", page, _re.S)
    assert block, "no cloning-oligos block in the page"
    body = block.group(1)
    assert "HDR donor" in body, "the oligo block omits the repair template"
    assert "&quot;kind&quot;" not in body, "the oligo record is still dumped as JSON"
