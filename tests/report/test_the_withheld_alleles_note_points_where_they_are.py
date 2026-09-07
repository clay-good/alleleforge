"""The renders said the withheld alleles were "in the lossless export". They were not.

A Cas9 candidate's indel spectrum routinely has 65 alleles; the report shows three and
says so:

    showing 3 of 65 predicted alleles (0.15 of the probability mass);
    the rest are in the lossless export.

`--format json` writes `report_to_json`, which serializes the `DesignReport` — and the
report's `outcome_top` is the *same three*. A reader chasing the other 62 opened the
export and found what was already on the page.

The full spectrum lives one level up, on the `RankedMenu`: `menu_to_json`, or
`aforge design --json`. The note now says that. Pinned as a fact about the data, not a
string match: the report export really does truncate and the menu really does not, so if
either ever changes the note becomes wrong and this fails.
"""

from __future__ import annotations

import json
import re

import pytest

from alleleforge.report.builder import WITHHELD_ALLELES_NOTE, build_report
from alleleforge.report.export import menu_to_json, report_to_json
from alleleforge.report.html import render_html
from alleleforge.report.pdf import render_pdf
from alleleforge.types.candidate import RankedMenu


@pytest.fixture
def truncating_report(prime_menu: RankedMenu) -> object:
    report = build_report(prime_menu, top_alleles=1)
    assert any(c.n_outcome_alleles > len(c.outcome_top) for c in report.candidates), (
        "nothing was withheld — this file would be vacuous"
    )
    return report


def test_the_report_export_does_not_carry_the_withheld_alleles(
    truncating_report: object,
) -> None:
    """The defect. If this ever fails, the note below is the thing to change."""
    payload = json.loads(report_to_json(truncating_report))
    assert any(len(c["outcome_top"]) < c["n_outcome_alleles"] for c in payload["candidates"])


def test_the_menu_export_does_carry_them(prime_menu: RankedMenu) -> None:
    """The claim the note now makes, checked against the same numbers."""
    report = build_report(prime_menu, top_alleles=1)
    menu = json.loads(menu_to_json(prime_menu))
    counts = {len(c["outcome"]["alleles"]) for c in menu["candidates"] if c.get("outcome")}
    reported = {c.n_outcome_alleles for c in report.candidates if c.n_outcome_alleles}
    assert counts == reported, (counts, reported)


def test_both_renders_send_the_reader_to_the_menu(truncating_report: object) -> None:
    assert WITHHELD_ALLELES_NOTE in render_html(truncating_report).replace("&#x27;", "'")
    # The PDF hard-wraps to its column width, so the sentence is reassembled from the
    # text runs rather than matched as a fragment. Before this round the PDF said the
    # count and nothing about where the rest went, so it is pinned whole.
    # cp1252, not latin-1: the writer encodes the note's em dash as 0x97, which is an
    # em dash in cp1252 and an unprintable control character in latin-1.
    text = render_pdf(truncating_report).decode("cp1252", errors="ignore")
    runs = re.findall(r"\((.*?)\) Tj", text)
    prose = " ".join(run.replace("\\(", "(").replace("\\)", ")") for run in runs)
    prose = " ".join(prose.split())
    assert WITHHELD_ALLELES_NOTE in prose


def test_the_note_does_not_call_the_report_export_lossless() -> None:
    assert "lossless" not in WITHHELD_ALLELES_NOTE
    assert "menu" in WITHHELD_ALLELES_NOTE
