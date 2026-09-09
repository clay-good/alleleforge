"""The helper the PDF assertions rest on, checked against the escaping it must undo."""

from __future__ import annotations

from alleleforge.report.builder import RESEARCH_USE_DISCLAIMER
from tests.pdf_text import pdf_runs, pdf_text


def _page(*runs: str) -> bytes:
    body = "\n".join(f"({run}) Tj" for run in runs)
    return f"BT\n{body}\nET".encode("cp1252")


def test_escaped_parentheses_come_back_as_parentheses() -> None:
    assert pdf_runs(_page(r"validated \(e.g. GUIDE-seq\) before use")) == [
        "validated (e.g. GUIDE-seq) before use"
    ]


def test_an_escaped_closing_paren_does_not_end_the_run() -> None:
    """The bug the shared regex had: `(a \\) b) Tj` is one run, not two."""
    assert pdf_runs(_page(r"showing 3 of 4 \(0.95 of the mass\); the rest")) == [
        "showing 3 of 4 (0.95 of the mass); the rest"
    ]


def test_the_prose_is_wrap_insensitive() -> None:
    assert pdf_text(_page("the full spectrum is", "on the ranked   menu")) == (
        "the full spectrum is on the ranked menu"
    )


def test_the_disclaimer_survives_a_real_render(prime_menu: object) -> None:
    """The sentence every extractor was mangling, on a real page."""
    from alleleforge.report.builder import build_report
    from alleleforge.report.pdf import render_pdf

    assert "(e.g." in RESEARCH_USE_DISCLAIMER, RESEARCH_USE_DISCLAIMER
    rendered = pdf_text(render_pdf(build_report(prime_menu)))  # type: ignore[arg-type]
    assert RESEARCH_USE_DISCLAIMER in rendered, rendered[:400]
