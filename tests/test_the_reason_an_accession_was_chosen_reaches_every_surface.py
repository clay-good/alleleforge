"""What ClinVar says about the variant reached the prose surfaces and nothing else.

A ClinVar accession is looked up for its coordinates, but the coordinates are not why
anyone types `VCV000012345` — the classification is. The resolver carries the assertion
for exactly that reason, and it reached the menu rationale, and therefore the HTML, the
PDF and the report JSON, which render prose.

Every other surface dropped it:

* `aforge resolve`, whose entire job is saying what an input means, reported
  `source: clinvar` and not one word of what ClinVar said;
* the flat TSV and Parquet — a spreadsheet of pegRNAs correcting a variant ClinVar calls
  Benign reads exactly like one correcting a pathogenic allele;
* the cohort summary, which is the run a cohort of accessions produces, triaged by
  scanning hundreds of rows that nobody expands into per-item rationales.

Pinned per surface rather than corpus-wide: a fact present *somewhere* is what let this
sit behind a set of tests about clinical assertions that all passed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app

_SEQ = "ACGTTGCAAGGCTTACCGTA" * 30
_ACCESSION = "VCV000000012"


@pytest.fixture
def workspace(tmp_path: Path) -> tuple[Path, Path]:
    """A reference and a one-record ClinVar release calling the variant pathogenic."""
    assert _SEQ[102] == "G"
    fasta = tmp_path / "chr9.fa"
    fasta.write_text(">chr9\n" + _SEQ + "\n")
    vcf = tmp_path / "clinvar.vcf"
    vcf.write_text(
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        "9\t103\t12\tG\tA\t.\t.\tCLNSIG=Pathogenic;CLNREVSTAT=reviewed_by_expert_panel\n"
    )
    return fasta, vcf


def test_resolve_reports_what_the_database_asserted(workspace: tuple[Path, Path]) -> None:
    fasta, vcf = workspace
    result = CliRunner().invoke(
        app,
        ["resolve", _ACCESSION, "--reference-fasta", str(fasta), "--clinvar", str(vcf), "--json"],
    )
    assert result.exit_code == 0, result.output + result.stderr
    payload = json.loads(result.stdout)
    assert payload["clinical_significance"] == "pathogenic", payload
    # The class alone is not the claim; the review status is the evidence behind it.
    assert payload["clinical_review_status"] == "reviewed by expert panel", payload


def test_a_coordinate_input_asserts_nothing_rather_than_guessing(
    workspace: tuple[Path, Path],
) -> None:
    """`None` must mean "no database asserted anything", not "benign"."""
    fasta, _ = workspace
    result = CliRunner().invoke(
        app, ["resolve", "chr9:103:G>A", "--reference-fasta", str(fasta), "--json"]
    )
    payload = json.loads(result.stdout)
    assert payload["clinical_significance"] is None, payload


def _design(workspace: tuple[Path, Path], tmp_path: Path, fmt: str) -> str:
    fasta, vcf = workspace
    out = tmp_path / f"menu.{fmt}"
    result = CliRunner().invoke(
        app,
        [
            "design",
            _ACCESSION,
            "--reference-fasta",
            str(fasta),
            "--clinvar",
            str(vcf),
            "--no-offtarget",
            "--format",
            fmt,
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    return out.read_text(encoding="utf-8")


@pytest.mark.parametrize("fmt", ["tsv", "html", "json"])
def test_every_rendered_format_states_the_classification(
    fmt: str, workspace: tuple[Path, Path], tmp_path: Path
) -> None:
    assert "pathogenic" in _design(workspace, tmp_path, fmt).lower()


def test_the_parquet_carries_it_too(workspace: tuple[Path, Path], tmp_path: Path) -> None:
    pl = pytest.importorskip("polars")
    fasta, vcf = workspace
    out = tmp_path / "menu.parquet"
    result = CliRunner().invoke(
        app,
        [
            "design",
            _ACCESSION,
            "--reference-fasta",
            str(fasta),
            "--clinvar",
            str(vcf),
            "--no-offtarget",
            "--format",
            "parquet",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    notes = " ".join(v for k, v in pl.read_parquet_metadata(out).items() if k.startswith("note_"))
    assert "pathogenic" in notes.lower(), notes


def test_the_cohort_summary_has_a_column_for_it(
    workspace: tuple[Path, Path], tmp_path: Path
) -> None:
    fasta, vcf = workspace
    listing = tmp_path / "cohort.txt"
    listing.write_text(f"{_ACCESSION}\nchr9:103:G>A\n")
    summary = tmp_path / "summary.tsv"
    result = CliRunner().invoke(
        app,
        [
            "batch",
            str(listing),
            "--reference-fasta",
            str(fasta),
            "--clinvar",
            str(vcf),
            "--no-offtarget",
            "--summary-tsv",
            str(summary),
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    rows = [ln for ln in summary.read_text().splitlines() if not ln.startswith("#")]
    header = rows[0].split("\t")
    assert "clinical_significance" in header, header
    column = header.index("clinical_significance")
    cells = [r.split("\t")[column] for r in rows[1:]]
    # The accession carries it; the bare coordinate asserts nothing and stays empty.
    assert cells == ["pathogenic", ""], cells
