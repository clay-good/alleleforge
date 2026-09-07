""" "2 nominated site(s)" is the number a reader acts on and the one they cannot check.

The report carries no per-site rows — by design, it summarises — so a candidate's
off-target section gives a count, a specificity, the scorer, the matrix and the search
budget, and nothing that says *which* two sites. `--format json` writes that same
summary: `report_to_json` serializes the `DesignReport`, whose `CandidateReport` has
`n_offtarget_sites` and no `sites`. A code comment beside the summary said "the lossless
export has the sites", which is true of the ranked menu one level up and not of the file
the reader most likely opened.

For a safety artifact this is the wrong thing to leave implicit. A site count without a
route to the sites is a number a reader has to take on faith, and the whole design of this
report is to avoid exactly that.

The note appears only where there are sites: with none nominated there is nothing to go
and read, and a line that always fires is a line nobody reads.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.report.builder import (
    NOMINATED_SITES_NOTE,
    RANKED_MENU_SOURCE,
    WITHHELD_ALLELES_NOTE,
    build_report,
)
from alleleforge.report.export import menu_to_json, report_to_json
from alleleforge.report.html import render_html
from alleleforge.report.pdf import render_pdf
from alleleforge.types.edit import EditIntent

_SPACER = "ACCTGAAGACTTACGCATAC"


@pytest.fixture
def searched(tmp_path: Path) -> tuple[object, object]:
    """A menu whose search nominates at least one site, and the menu itself."""
    rng = random.Random(3)
    seq = [rng.choice("ACGT") for _ in range(3_000)]
    seq[1000:1023] = list(_SPACER + "TGG")
    # A near-identical decoy elsewhere on the contig, so a real site is nominated.
    seq[2000:2023] = list(_SPACER[:18] + "GG" + "TGG")
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr1\n" + "".join(seq) + "\n")
    menu = design(
        "chr1:1018:T>A",
        reference=ReferenceGenome(fasta, build="hg38"),
        intent=EditIntent.KNOCK_OUT,
    )
    report = build_report(menu)
    assert any(c.n_offtarget_sites for c in report.candidates), "no site was nominated"
    return menu, report


def test_the_report_export_really_has_no_site_rows(searched: tuple[object, object]) -> None:
    """The premise. If this changes, the note is what should change with it."""
    _, report = searched
    payload = json.loads(report_to_json(report))
    for candidate in payload["candidates"]:
        assert "sites" not in candidate, sorted(candidate)
    assert any(c.get("n_offtarget_sites") for c in payload["candidates"])


def test_the_menu_export_does_have_them(searched: tuple[object, object]) -> None:
    menu, report = searched
    payload = json.loads(menu_to_json(menu))
    counts = {len(c["offtarget"]["sites"]) for c in payload["candidates"] if c.get("offtarget")}
    reported = {c.n_offtarget_sites for c in report.candidates if c.n_offtarget_sites}
    assert reported <= counts, (reported, counts)


def test_both_renders_say_where_the_sites_are(searched: tuple[object, object]) -> None:
    _, report = searched
    html = render_html(report).replace("&#x27;", "'").replace("&gt;", ">")
    assert "the site rows" in html, "the HTML never says where the sites are"

    runs = re.findall(r"\((.*?)\) Tj", render_pdf(report).decode("cp1252", errors="ignore"))
    prose = " ".join(" ".join(runs).split())
    assert NOMINATED_SITES_NOTE in prose, prose[:400]


def test_a_candidate_with_no_sites_carries_no_note(tmp_path: Path) -> None:
    """Nothing was nominated, so there is nothing to go and read."""
    rng = random.Random(11)
    contig = "".join(rng.choice("ACGT") for _ in range(1_500))
    fasta = tmp_path / "quiet.fa"
    fasta.write_text(">chr2\n" + contig + "\n")
    # The ref base read off the contig, so the fixture cannot drift from the sequence.
    menu = design(
        f"chr2:750:{contig[749]}>{'A' if contig[749] != 'A' else 'C'}",
        reference=ReferenceGenome(fasta, build="hg38"),
        run_offtarget=False,
        intent=EditIntent.KNOCK_OUT,
    )
    report = build_report(menu)
    assert all(not c.n_offtarget_sites for c in report.candidates)
    assert "the site rows" not in render_html(report)


def test_the_two_notes_point_at_the_same_place() -> None:
    """Alleles and sites are withheld from the same export for the same reason."""
    assert RANKED_MENU_SOURCE in NOMINATED_SITES_NOTE
    assert RANKED_MENU_SOURCE in WITHHELD_ALLELES_NOTE
    assert "lossless" not in NOMINATED_SITES_NOTE
