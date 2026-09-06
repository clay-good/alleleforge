"""`aforge verify` must accept the provenance sidecar `aforge design` writes.

`design --out X` writes the result to `X` and a `X.provenance.json` sidecar holding the
run's `Provenance` block. `verify` calls itself the command that "turns provenance from a
record into a checkable contract" -- but it only ever parsed a full `RankedMenu`, so
handing it that sidecar failed with a pydantic error about a missing `candidates` field.

That is not a cosmetic gap. For `--format tsv`, `html` and `pdf` -- three of the four
output formats -- the sidecar is the *only* machine-readable provenance the run produces.
The contract was unreachable for every one of them, and the way it failed pointed the
user at the wrong thing: nothing is wrong with the sidecar.

Every check `verify` performs reads `prov` and nothing else, so accepting the block on
its own is the whole fix. What must stay true is that a file which is neither shape is
still rejected, and says which two shapes are accepted.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def prime_fasta(tmp_path: Path) -> Path:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    fasta = tmp_path / "prime.fa"
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    return fasta


def _design(runner: CliRunner, fasta: Path, out: Path, fmt: str) -> None:
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(fasta),
            "--intent",
            "install",
            "--max-per-chemistry",
            "1",
            "--format",
            fmt,
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize("fmt", ["json", "tsv", "html"])
def test_the_sidecar_of_every_format_verifies(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path, fmt: str
) -> None:
    """The sidecar a run writes is verifiable, whatever format the result took."""
    out = tmp_path / f"menu.{fmt}"
    _design(runner, prime_fasta, out, fmt)
    sidecar = out.with_suffix(out.suffix + ".provenance.json")
    assert sidecar.is_file()

    result = runner.invoke(app, ["verify", str(sidecar), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["verified"] is True
    assert payload["alleleforge_version"]
    assert payload["n_models"] >= 1


def test_sidecar_and_result_verify_to_the_same_report(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    """Reading the block alone reaches the same verdict as reading the whole result."""
    out = tmp_path / "menu.json"
    _design(runner, prime_fasta, out, "json")
    sidecar = out.with_suffix(out.suffix + ".provenance.json")

    from_result = json.loads(runner.invoke(app, ["verify", str(out), "--json"]).stdout)
    from_sidecar = json.loads(runner.invoke(app, ["verify", str(sidecar), "--json"]).stdout)
    assert from_result == from_sidecar


def test_a_file_that_is_neither_shape_is_still_rejected(runner: CliRunner, tmp_path: Path) -> None:
    """Widening the input must not widen it to anything; the error names both shapes."""
    junk = tmp_path / "junk.json"
    junk.write_text('{"hello": "world"}')

    result = runner.invoke(app, ["verify", str(junk)])
    assert result.exit_code == ExitCode.USAGE
    combined = result.output + result.stderr
    assert "result" in combined and "provenance" in combined


def test_a_result_without_provenance_is_still_unverifiable(
    runner: CliRunner, tmp_path: Path
) -> None:
    """A menu carrying no provenance block must not be mistaken for a bare block."""
    menu = tmp_path / "menu.json"
    menu.write_text(json.dumps({"schema_version": 5, "candidates": [], "provenance": None}))

    result = runner.invoke(app, ["verify", str(menu)])
    assert result.exit_code == ExitCode.UNAVAILABLE
    assert "no provenance" in (result.output + result.stderr)
