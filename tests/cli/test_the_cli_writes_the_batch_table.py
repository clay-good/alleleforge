"""`aforge design --format parquet` — the format the CLI documented and could not write.

`docs/api/cli.md` describes the Parquet export in the `--format` section, down to the
metadata keys and the `polars>=1.30` floor. `--format` accepted `json|tsv|html|pdf`.
`report_to_parquet` was reachable from Python alone, so the round that gave Parquet its
disclaimer, reference build and coordinate convention improved a file no shell could
produce.

Parquet's notes live in file-level metadata, so it requires `--out` like the other two
formats a terminal cannot usefully receive, and the provenance sidecar every written
artifact gets is written here too — a new format taking its own write path is exactly
how a sidecar goes missing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app
from alleleforge.report.export import TSV_COLUMNS


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    path = tmp_path / "prime.fa"
    path.write_text(">chr2\n" + "".join(seq) + "\n")
    return path


def _design(runner: CliRunner, fasta: Path, *extra: str) -> tuple[int, str]:
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(fasta),
            "--no-offtarget",
            "--format",
            "parquet",
            *extra,
        ],
    )
    return result.exit_code, result.output + result.stderr


def test_the_cli_writes_a_parquet_carrying_its_notes(
    runner: CliRunner, fasta: Path, tmp_path: Path
) -> None:
    pl = pytest.importorskip("polars")
    out = tmp_path / "menu.parquet"
    code, output = _design(runner, fasta, "--out", str(out))
    assert code == 0, output
    assert out.exists()

    frame = pl.read_parquet(out)
    assert frame.height > 0
    assert frame.columns == list(TSV_COLUMNS)

    metadata = pl.read_parquet_metadata(out)
    assert "research tool" in metadata["disclaimer"]
    notes = " ".join(v for k, v in metadata.items() if k.startswith("provenance_"))
    assert "hg38" in notes and "0-based" in notes


def test_the_parquet_gets_the_same_provenance_sidecar_every_format_gets(
    runner: CliRunner, fasta: Path, tmp_path: Path
) -> None:
    pytest.importorskip("polars")
    out = tmp_path / "menu.parquet"
    code, output = _design(runner, fasta, "--out", str(out))
    assert code == 0, output
    sidecar = out.with_suffix(out.suffix + ".provenance.json")
    assert sidecar.exists(), output
    assert str(sidecar) in output
    assert json.loads(sidecar.read_text())["config_snapshot"]


def test_parquet_without_out_is_a_usage_error(runner: CliRunner, fasta: Path) -> None:
    """A binary columnar file is not something a terminal can receive."""
    code, output = _design(runner, fasta)
    assert code == ExitCode.USAGE
    assert "--out" in output
