"""`verify` answered the most natural mistake with a pydantic stack dump.

`aforge design --format html` ends by printing:

    wrote report.html and report.html.provenance.json

The obvious next command is `aforge verify report.html`. That produced three stacked
validation errors, `errors.pydantic.dev` links included, beginning "Invalid JSON:
expected value at line 1 column 1".

The tool already knew the answer. `verify`'s own docstring says that for tsv, html and pdf
"the sidecar is the only machine-readable provenance a run leaves behind" — which is why
it accepts a bare sidecar at all. The refusal did not say it, so the one path a user is
most likely to take out of that mistake was the one thing missing from the error.

The detailed refusal is kept for a file that really is malformed JSON with no sidecar
beside it: that user needs the validator's output, and this one needs a next command.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def rendered(tmp_path: Path) -> Path:
    """A real `design --format html` run: the artifact and its sidecar."""
    rng = random.Random(11)
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "".join(rng.choice("ACGT") for _ in range(3_000)) + "\n")
    out = tmp_path / "report.html"
    result = CliRunner().invoke(
        app,
        [
            "design",
            "chr2:1050:G>A",
            "--reference-fasta",
            str(fasta),
            "--format",
            "html",
            "--out",
            str(out),
            "--no-offtarget",
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    assert out.is_file() and out.with_name(f"{out.name}.provenance.json").is_file()
    return out


def test_the_refusal_names_the_file_that_would_work(runner: CliRunner, rendered: Path) -> None:
    result = runner.invoke(app, ["verify", str(rendered)])
    assert result.exit_code != 0
    assert "provenance is written to a sidecar" in result.stderr
    assert str(rendered.with_name(f"{rendered.name}.provenance.json")) in result.stderr
    assert "pydantic.dev" not in result.stderr, "the stack dump is not the answer here"


def test_the_named_command_actually_works(runner: CliRunner, rendered: Path) -> None:
    """A remedy that has not been run is a guess."""
    sidecar = rendered.with_name(f"{rendered.name}.provenance.json")
    result = runner.invoke(app, ["verify", str(sidecar)])
    assert result.exit_code == 0, result.output + result.stderr
    assert "verified" in result.output


def test_a_malformed_file_with_no_sidecar_still_gets_the_detail(
    runner: CliRunner, tmp_path: Path
) -> None:
    """That caller needs the validator's output; there is no next command to name."""
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"nope": 1}))
    result = runner.invoke(app, ["verify", str(bad)])
    assert result.exit_code != 0
    assert "not a design report, a ranked menu, or a provenance sidecar" in result.stderr
