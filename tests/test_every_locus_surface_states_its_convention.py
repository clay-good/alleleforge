"""`resolve` printed loci and never said which convention they were in.

Off-by-one between 0-based half-open (what this tool emits) and 1-based inclusive (what a
genome browser shows) is the error this project has a named constant for. The report
footer, the cohort TSV header, the off-target command and the off-target endpoint all
carry `COORDINATE_NOTE` / `coordinate_system`.

`resolve` did not — the command whose entire job is telling a caller what their input
means, whose output is a normalized variant position and a working interval, and which the
docs describe as the debugging aid. A user pasting `chr1:144499899-144500100` into a
browser lands one base off, and nothing on the page warned them.

This pins the convention onto every surface that emits a locus, in both forms, rather
than onto the one that prompted the fix.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from alleleforge.cli.main import app
from alleleforge.report.builder import COORDINATE_NOTE, COORDINATE_SYSTEM

VARIANT = "chr7:5530600:A>G"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_the_human_resolve_states_the_convention(runner: CliRunner) -> None:
    result = runner.invoke(app, ["resolve", VARIANT])
    assert result.exit_code == 0, result.output
    assert "working interval:" in result.output
    assert COORDINATE_NOTE in result.output


def test_the_json_resolve_names_the_system(runner: CliRunner) -> None:
    result = runner.invoke(app, ["resolve", VARIANT, "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["coordinate_system"] == COORDINATE_SYSTEM


def test_the_resolve_endpoint_names_it_too() -> None:
    from alleleforge.web.api.app import create_app

    body = (
        TestClient(create_app())
        .post("/api/resolve", json={"variant": VARIANT, "build": "hg38"})
        .json()
    )
    assert body["coordinate_system"] == COORDINATE_SYSTEM


def test_the_offtarget_surfaces_still_do(runner: CliRunner, tmp_path: object) -> None:
    """The surfaces that already stated it must keep stating it."""
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "ACGT" * 40 + "\n")
    human = runner.invoke(
        app, ["offtarget", "GACCATGCAACCTTGAACGT", "--reference-fasta", str(fasta)]
    )
    assert COORDINATE_NOTE in human.output
    machine = runner.invoke(
        app,
        ["offtarget", "GACCATGCAACCTTGAACGT", "--reference-fasta", str(fasta), "--json"],
    )
    assert json.loads(machine.stdout)["coordinate_system"] == COORDINATE_SYSTEM
