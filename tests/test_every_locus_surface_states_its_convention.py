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
from alleleforge.report.builder import (
    COORDINATE_NOTE,
    COORDINATE_SYSTEM,
    VARIANT_POSITION_NOTE,
)

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


def test_resolve_warns_that_its_own_output_is_not_its_own_input(runner: CliRunner) -> None:
    """The one printed locus that does not round-trip, on the surface built to print it.

    `COORDINATE_NOTE` is a statement about loci, and intervals really do go back in
    unchanged. A *variant* does not: it is read as a 1-based VCF record and printed
    0-based, so `resolve chr1:1018:T>A` answers `chr1:1017:T>A`. Pasting that back either
    fails the reference check or, when the neighbouring base happens to match, designs an
    edit one base away.

    `resolve` is the command whose entire purpose is handing a caller a normalized
    variant, which makes it the surface most likely to have its output pasted straight
    back in — and it was the last one saying nothing, after the refusal and both renders
    had been given the sentence.
    """
    result = runner.invoke(app, ["resolve", VARIANT])
    assert result.exit_code == 0, result.output
    assert VARIANT_POSITION_NOTE in result.output, result.output
    # Beside the number, not appended to the end of an unrelated paragraph.
    lines = result.output.splitlines()
    variant_line = next(i for i, line in enumerate(lines) if line.startswith("chr7:"))
    assert VARIANT_POSITION_NOTE in lines[variant_line + 1], lines[: variant_line + 3]


def test_the_note_says_what_to_do_not_only_that_it_differs() -> None:
    """A convention statement a reader cannot act on is trivia."""
    assert "add 1" in VARIANT_POSITION_NOTE
    assert "1-based" in VARIANT_POSITION_NOTE and "0-based" in VARIANT_POSITION_NOTE
