"""A fact about the run, in a paragraph about a candidate.

`aforge design --format html --out r.html` against a gnomAD file built for another assembly
printed exactly this:

    wrote r.html and r.html.provenance.json

The disclosure existed — as the sixth clause of each candidate's `offtarget_search`
paragraph, repeated once per reagent, in the same neutral style as the PAM broadening. The
off-target surfaces lift such clauses onto their headline and the cohort surfaces onto their
note block; a design report had no run-level channel for them at all, which is the third
surface of one class and the one where the reader is furthest from the sentence.

`DesignReport.notes` is that channel, built through the same `headline_notes` the off-target
surfaces use, deduplicated because it is a fact about the run and not about each of forty
reagents. The guard's population is every rendering of a design report, so a render added
later fails until it carries them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from alleleforge.data.gnomad import GnomadDB
from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.report import build_report
from alleleforge.report.export import report_to_json, report_to_tsv
from alleleforge.report.html import render_html
from alleleforge.report.pdf import render_pdf

_ALT = {"A": "G", "G": "A", "C": "T", "T": "C"}


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    import random

    random.seed(11)
    seq = list("".join(random.choice("ACGT") for _ in range(4000)))
    seq[1000:1023] = list("ACCTGACTCCTGAGGAGAAG" + "TGG")
    body = "".join(seq)
    path = tmp_path / "ref.fa"
    path.write_text(
        ">chr11\n" + "\n".join(body[i : i + 60] for i in range(0, len(body), 60)) + "\n"
    )
    return path


def _base(fasta: Path, one_based: int) -> str:
    import pyfaidx

    return str(pyfaidx.Fasta(str(fasta))["chr11"][one_based - 1 : one_based]).upper()


def _report(fasta: Path, tmp_path: Path, *, agreeing: bool) -> Any:
    rows = []
    for pos in (1100, 1200):
        base = _base(fasta, pos)
        ref, alt = (base, _ALT[base]) if agreeing else (_ALT[base], base)
        rows.append(f"chr11\t{pos}\t{ref}\t{alt}\t0.02\t0.055\t0.0008")
    sites = tmp_path / f"{'right' if agreeing else 'wrong'}.tsv"
    sites.write_text("#chrom\tpos\tref\talt\taf\tafr\tnfe\n" + "\n".join(rows) + "\n")
    variant = f"chr11:1005:{_base(fasta, 1005)}>{_ALT[_base(fasta, 1005)]}"
    menu = design(
        variant,
        reference=ReferenceGenome(fasta, build="hg38"),
        gnomad=GnomadDB.from_sites_tsv(sites),
        populations=["afr", "nfe"],
    )
    return build_report(menu, variant=variant, intent="correct")


def test_the_report_carries_the_run_level_note(fasta: Path, tmp_path: Path) -> None:
    report = _report(fasta, tmp_path, agreeing=False)
    assert any("another build" in note for note in report.notes), report.notes


def test_it_is_said_once_however_many_candidates(fasta: Path, tmp_path: Path) -> None:
    """A fact about the run, not about each of forty reagents."""
    report = _report(fasta, tmp_path, agreeing=False)
    assert len(report.notes) == len(set(report.notes))
    assert len(report.candidates) > 1, "one candidate cannot show a duplicate"


def test_a_run_with_nothing_to_qualify_says_nothing(fasta: Path, tmp_path: Path) -> None:
    report = _report(fasta, tmp_path, agreeing=True)
    assert not [note for note in report.notes if "another build" in note]


@pytest.mark.parametrize("render", ["json", "tsv", "html", "pdf"])
def test_every_render_carries_them(render: str, fasta: Path, tmp_path: Path) -> None:
    report = _report(fasta, tmp_path, agreeing=False)
    assert report.notes, "the fixture no longer qualifies anything"
    body: str = {
        "json": lambda: report_to_json(report),
        "tsv": lambda: report_to_tsv(report),
        "html": lambda: render_html(report),
        "pdf": lambda: render_pdf(report).decode("latin-1", "replace"),
    }[render]()
    for note in report.notes:
        # The PDF wraps at a column width, so compare on a distinctive fragment.
        assert "another build" in body, f"{render} does not carry {note!r}"


def test_the_html_puts_it_where_a_reader_looks(fasta: Path, tmp_path: Path) -> None:
    """Above the rationale and in the hazard style, beside the missing-menu block."""
    report = _report(fasta, tmp_path, agreeing=False)
    body = render_html(report)
    index = body.index("About this run, not about a candidate")
    assert "hazard" in body[max(0, index - 120) : index]
    assert index < body.index("How this menu was assembled")


def test_the_cli_prints_them_beside_the_receipt() -> None:
    """`--out` makes the file the document and the terminal a receipt; `wrote r.html` was
    the entire output of a run whose population source was for another assembly."""
    from alleleforge.cli import main as cli_main

    source = Path(cli_main.__file__).read_text(encoding="utf-8")
    assert "for note in report.notes:" in source


def test_the_menu_owns_the_derivation(fasta: Path, tmp_path: Path) -> None:
    """One derivation, not two.

    `build_report` used to walk the candidates itself. A menu written by `--output-dir`
    is the surface where a reader is furthest from any sentence — one file out of five
    hundred in a directory — and it carried the *count* (`source_build_mismatch`) with no
    statement anywhere. Putting the derivation on `RankedMenu` gives the per-item file,
    the Python caller and the report one answer instead of the report having its own.
    """
    report = _report(fasta, tmp_path, agreeing=False)
    assert report.notes, "the fixture no longer qualifies anything"

    from alleleforge.report import build_report as _build

    menu = design(
        report.variant,
        reference=ReferenceGenome(fasta, build="hg38"),
        gnomad=GnomadDB.from_sites_tsv(tmp_path / "wrong.tsv"),
        populations=["afr", "nfe"],
    )
    assert menu.notes == report.notes
    assert _build(menu, variant=report.variant, intent="correct").notes == menu.notes


def test_a_per_item_menu_file_carries_them(fasta: Path, tmp_path: Path) -> None:
    """The surface the cohort's own exemption assumed had context beside it."""
    import json

    report = _report(fasta, tmp_path, agreeing=False)
    menu = design(
        report.variant,
        reference=ReferenceGenome(fasta, build="hg38"),
        gnomad=GnomadDB.from_sites_tsv(tmp_path / "wrong.tsv"),
        populations=["afr", "nfe"],
    )
    written = json.loads(menu.model_dump_json())
    assert any("another build" in note for note in written["notes"]), written["notes"]
