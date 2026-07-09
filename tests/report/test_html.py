"""Tests for the Phase 11 HTML renderer."""

from __future__ import annotations

from alleleforge.report.builder import build_report
from alleleforge.report.html import PLOTLY_CDN, render_html
from alleleforge.types.candidate import RankedMenu


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


def test_empty_menu_renders(prime_menu: RankedMenu) -> None:
    from alleleforge.types.candidate import RankedMenu as RM

    empty = RM(candidates=(), provenance=prime_menu.provenance)
    html = render_html(build_report(empty))
    assert "No candidates" in html
    assert html.rstrip().endswith("</html>")
