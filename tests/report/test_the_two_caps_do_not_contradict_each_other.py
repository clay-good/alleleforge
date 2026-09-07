"""One page said 30 candidates are missing from the exports, and that none are.

This report has two caps and they mean opposite things about the data.

`max_candidates_per_chemistry` is a **data** cap: it removes candidates during ranking,
before the menu exists, so they are in no export. Its note says exactly that — "30
lower-ranked candidate(s) were dropped and are not in this result or its exports".

The render cap is a **display** cap: the page draws the top 50 plus the Pareto front, and
everything is still in the exports. Its note used to say "no export is capped — every
candidate is in the JSON report", which is true of the render cap and a blanket claim
about exports.

With `--max-per-chemistry 60` on a 90-candidate menu both fire, and a reader gets both
sentences on one page. Scoping the second to *this menu* makes them true together, which
they always were — the sentence was describing one cap in language that covered both.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.report.builder import WITHHELD_CANDIDATES_NOTE, build_report
from alleleforge.report.html import render_html


@pytest.fixture
def both_caps_fire(tmp_path: Path) -> str:
    """A report where the data cap dropped candidates *and* the render cap withheld some."""
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    reference = ReferenceGenome(fasta, build="hg38")
    uncapped = design("chr2:71:A>C", reference=reference, run_offtarget=False)
    assert len(uncapped.candidates) > 60, len(uncapped.candidates)
    capped = design(
        "chr2:71:A>C",
        reference=reference,
        run_offtarget=False,
        max_candidates_per_chemistry=60,
    )
    assert len(capped.candidates) == 60
    page = html.unescape(re.sub(r"<[^>]+>", " ", render_html(build_report(capped))))
    return " ".join(page.split())


def test_both_notes_really_are_on_the_page(both_caps_fire: str) -> None:
    """Without the collision there is nothing here to reconcile."""
    assert "not in this result or its exports" in both_caps_fire
    assert "Showing 50 of 60 candidates" in both_caps_fire


def test_the_render_cap_does_not_claim_the_exports_are_complete(both_caps_fire: str) -> None:
    assert "no export is capped" not in both_caps_fire
    assert WITHHELD_CANDIDATES_NOTE in both_caps_fire


def test_the_render_cap_note_scopes_itself_to_this_menu() -> None:
    note = WITHHELD_CANDIDATES_NOTE
    assert "in this menu" in note, note
    assert "render cap" in note, note
    for name in ("JSON", "TSV", "Parquet"):
        assert name in note, note


def test_the_data_cap_still_says_its_candidates_are_gone(both_caps_fire: str) -> None:
    """Scoping one sentence must not soften the other: those 30 really are unrecoverable."""
    assert "30 lower-ranked candidate(s) were dropped" in both_caps_fire
