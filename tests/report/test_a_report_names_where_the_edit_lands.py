"""Every placed candidate must say *where* in the genome it edits.

A prior round added a provenance note stating the report's coordinates are 0-based
half-open, on the reasoning that "a printed cut site is the number a reader pastes into
a genome browser." The convention was labelled -- and then the coordinates themselves
were audited. What a reader actually got was:

* SpCas9: ``cut 117`` inside the reagent line -- a bare integer with **no contig**;
* prime editing: no genomic coordinate at all, five candidates differing only in RTT
  length and none saying where the edit lands;
* base editing: an activity window in protospacer-relative positions, no locus.

Rendering both fixture reports and searching the whole page for a contig name returned
nothing: no `chr...` token appeared anywhere in a report, while the provenance block
described the convention those absent coordinates were in. A locus without its contig
cannot be opened in a browser and is not even unique in a cohort report spanning genes.

These pin the locus at the three surfaces a reader or a pipeline reads it from.
"""

from __future__ import annotations

import re

import pytest

from alleleforge.report.builder import build_report
from alleleforge.report.export import TSV_COLUMNS, report_to_tsv
from alleleforge.report.html import render_html
from alleleforge.report.pdf import render_pdf
from alleleforge.types.candidate import RankedMenu

#: The check that first surfaced this: a contig token anywhere on the page.
CONTIG = re.compile(r"chr[0-9XYM]+")


@pytest.mark.parametrize("fixture", ["prime_menu", "ancestry_menu"])
def test_a_rendered_report_names_a_contig(fixture: str, request: pytest.FixtureRequest) -> None:
    menu: RankedMenu = request.getfixturevalue(fixture)
    page = render_html(build_report(menu))
    assert CONTIG.search(page), (
        "no contig name appears anywhere in the rendered report; a coordinate with no "
        "chromosome cannot be opened in a genome browser"
    )


@pytest.mark.parametrize("fixture", ["prime_menu", "ancestry_menu"])
def test_every_placed_candidate_carries_a_locus(
    fixture: str, request: pytest.FixtureRequest
) -> None:
    menu: RankedMenu = request.getfixturevalue(fixture)
    report = build_report(menu)
    assert report.candidates, "no candidates -- this check would be vacuous"
    for c in report.candidates:
        assert c.locus is not None, f"rank {c.rank} ({c.chemistry.value}) has no locus"
        assert CONTIG.match(c.locus), f"locus is not contig-qualified: {c.locus!r}"


def test_the_locus_states_the_position_a_reader_acts_on(ancestry_menu: RankedMenu) -> None:
    """The interval alone is not the actionable number; the cut/nick site is."""
    candidate = build_report(ancestry_menu).candidates[0]
    assert candidate.locus is not None
    assert "cut " in candidate.locus, candidate.locus
    # ...and it agrees with the reagent line, which printed it unqualified.
    cut = candidate.locus.split("cut ")[1]
    assert f"cut {cut}" in candidate.reagent


def test_the_prime_locus_names_the_nick(prime_menu: RankedMenu) -> None:
    candidate = build_report(prime_menu).candidates[0]
    assert candidate.locus is not None
    assert "nick " in candidate.locus, candidate.locus


@pytest.mark.parametrize("fixture", ["prime_menu", "ancestry_menu"])
def test_the_locus_reaches_the_printable_sheet(
    fixture: str, request: pytest.FixtureRequest
) -> None:
    """R183's lesson: the sheet a lab prints is where a field silently goes missing."""
    menu: RankedMenu = request.getfixturevalue(fixture)
    report = build_report(menu)
    locus = report.candidates[0].locus
    assert locus is not None
    page = render_pdf(report)
    # A PDF text string escapes `(` and `)`, so the strand parenthetical will not match
    # literally. Check the two halves that carry the information instead: the interval,
    # and the cut or nick position a reader acts on.
    interval, _, tail = locus.partition(" (")
    assert interval.encode() in page, f"{interval!r} missing from the printable sheet"
    site = tail.split(", ", 1)[1]
    assert site.encode() in page, f"{site!r} missing from the printable sheet"


def test_the_locus_is_an_export_column(ancestry_menu: RankedMenu) -> None:
    """A pipeline cannot join a candidate row to anything genomic without it."""
    assert "locus" in TSV_COLUMNS
    report = build_report(ancestry_menu)
    header, first = report_to_tsv(report).splitlines()[:2]
    cells = dict(zip(header.split("\t"), first.split("\t"), strict=True))
    assert cells["locus"] == report.candidates[0].locus


def test_an_unplaced_candidate_reports_no_locus(ancestry_menu: RankedMenu) -> None:
    """Guard the guard: the locus is read from a placement, not invented.

    A candidate with no placed reagent must say nothing rather than name a contig it
    does not have -- the failure direction that would make the new column untrustworthy.
    """
    from alleleforge.report.builder import _locus_summary
    from alleleforge.types.candidate import DesignCandidate
    from alleleforge.types.edit import Chemistry

    bare = DesignCandidate(chemistry=Chemistry.CAS9_NUCLEASE)
    assert _locus_summary(bare) is None


def test_the_readme_states_the_conventions_the_reports_actually_use() -> None:
    """The cheat-sheet said human-readable reports were 1-based. They are not.

    One row lumped HGVS together with "human-readable reports" and labelled the pair
    1-based. HGVS is; the reports are 0-based half-open, and say so in their own
    provenance block. A reader trusting the table would read the new `locus` as 1-based
    inclusive and land one base off -- the single failure this whole surface exists to
    prevent. Pinned, because the report note and the table are edited in different files.
    """
    from pathlib import Path

    from alleleforge.report.builder import COORDINATE_NOTE

    readme = (Path(__file__).resolve().parents[2] / "README.md").read_text()
    row = next(
        (line for line in readme.splitlines() if line.startswith("| Human-readable reports")),
        None,
    )
    assert row is not None, "the coordinate cheat-sheet has no row for the reports"
    assert "0-based half-open" in row, row
    assert "1-based" not in row.replace("0-based half-open", ""), row
    # ...and the report itself still says the same thing, so the two cannot drift apart.
    assert "0-based half-open" in COORDINATE_NOTE
