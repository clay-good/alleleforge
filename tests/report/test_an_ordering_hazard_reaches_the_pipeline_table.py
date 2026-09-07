"""An internal cloning site reached three surfaces and not the one that orders.

The oligo builder screens the insert for Type IIS sites and warns when it finds one:

    WARNING: internal-BsaI-site:pegrna-extension:+@27

That means the enzyme used to assemble the construct cuts the insert — a wet-lab failure
discovered after the DNA is paid for. It was rendered in the HTML, in the PDF and in the
JSON, and not in the TSV: the flat table a pipeline filters rows on before placing an
order. Sequences legitimately stay out of that table, being long and belonging in the
sheet; a short hazard string does not, and the table already carries `flags` as its
per-row hazard channel.

The column is empty when oligos were not requested, like every other conditional column,
so an absent warning is never confused with a screened-and-clean insert: `with_oligos`
decides whether the screen ran at all.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.report.builder import build_report
from alleleforge.report.export import TSV_COLUMNS, report_to_json, report_to_tsv
from alleleforge.report.html import render_html
from alleleforge.report.pdf import render_pdf


@pytest.fixture
def report_with_oligos(tmp_path: Path) -> object:
    rng = random.Random(11)
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "".join(rng.choice("ACGT") for _ in range(3_000)) + "\n")
    menu = design(
        "chr2:1050:G>A", reference=ReferenceGenome(fasta, build="hg38"), run_offtarget=False
    )
    return build_report(menu, with_oligos=True)


def _row(report: object) -> dict[str, str]:
    lines = [line for line in report_to_tsv(report).splitlines() if not line.startswith("#")]
    return dict(zip(lines[0].split("\t"), lines[1].split("\t"), strict=True))


def test_the_fixture_actually_trips_the_screen(report_with_oligos: object) -> None:
    """Without a real warning this whole test would pass vacuously."""
    warnings = report_with_oligos.candidates[0].oligos.warnings
    assert warnings, "the fixture no longer produces an oligo warning"
    assert any("internal" in w for w in warnings)


def test_the_hazard_reaches_every_surface(report_with_oligos: object) -> None:
    warning = report_with_oligos.candidates[0].oligos.warnings[0]
    assert warning in render_html(report_with_oligos)
    assert warning in render_pdf(report_with_oligos).decode("latin-1", errors="ignore")
    assert warning in report_to_json(report_with_oligos)
    assert warning in _row(report_with_oligos)["oligo_warnings"]


def test_the_column_exists_in_the_schema() -> None:
    assert "oligo_warnings" in TSV_COLUMNS


def test_a_report_without_oligos_leaves_it_empty(tmp_path: Path) -> None:
    """No screen was run, so the cell is empty rather than reassuringly clean."""
    rng = random.Random(11)
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "".join(rng.choice("ACGT") for _ in range(3_000)) + "\n")
    menu = design(
        "chr2:1050:G>A", reference=ReferenceGenome(fasta, build="hg38"), run_offtarget=False
    )
    assert _row(build_report(menu, with_oligos=False))["oligo_warnings"] == ""
