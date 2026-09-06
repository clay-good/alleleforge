"""An unchecked variant and a verified one were byte-identical.

Without a reference, `resolve` skips two things: left-alignment, and REF-allele
validation. With one, it does both. The proof:

    $ aforge resolve 'chr2:1006:T>A' --json          # genome has a G here
    {"variant": "chr2:1005:T>A", "variant_class": "snv", ...}      exit 0

    $ aforge resolve 'chr2:1006:T>A' --reference-fasta ref.fa
    error: reference mismatch at chr2:1005: asserted ref 'T' but reference has 'G'
    (wrong build?)

Same input, opposite epistemic status. And for a *correct* variant the two payloads were
byte-identical, so nothing in the artifact said whether the normalization had been checked
against a genome at all — the repo's most-repeated defect class, on the command whose whole
job is telling a caller what their input means.

`build` alone does not answer it either: it is a label the caller supplied, and it reads
`hg38` whether or not any FASTA was opened.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from alleleforge.cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    rng = random.Random(11)
    path = tmp_path / "ref.fa"
    path.write_text(">chr2\n" + "".join(rng.choice("ACGT") for _ in range(3_000)) + "\n")
    return path


def test_the_two_runs_are_no_longer_identical(runner: CliRunner, fasta: Path) -> None:
    checked = runner.invoke(
        app, ["resolve", "chr2:1006:G>A", "--reference-fasta", str(fasta), "--json"]
    )
    unchecked = runner.invoke(app, ["resolve", "chr2:1006:G>A", "--json"])
    assert checked.exit_code == unchecked.exit_code == 0
    assert checked.stdout != unchecked.stdout, (
        "a verified variant reads the same as an unverified one"
    )
    assert json.loads(checked.stdout)["reference_checked"] is True
    assert json.loads(unchecked.stdout)["reference_checked"] is False


def test_the_checked_payload_names_the_genome(runner: CliRunner, fasta: Path) -> None:
    """`build` is a label; two FASTAs both called hg38 are not the same genome."""
    payload = json.loads(
        runner.invoke(
            app, ["resolve", "chr2:1006:G>A", "--reference-fasta", str(fasta), "--json"]
        ).stdout
    )
    assert payload["reference"]["contigs"] == 1
    assert payload["reference"]["bases"] == 3_000
    assert payload["reference"]["sha256"]


def test_the_human_render_warns_when_nothing_was_checked(runner: CliRunner) -> None:
    output = runner.invoke(app, ["resolve", "chr2:1006:G>A"]).output
    assert "NOT checked against a" in output
    assert "--reference-fasta" in output


def test_the_human_render_says_what_verified_it(runner: CliRunner, fasta: Path) -> None:
    output = runner.invoke(
        app, ["resolve", "chr2:1006:G>A", "--reference-fasta", str(fasta)]
    ).output
    assert "the REF allele was verified against it" in output
    assert "NOT checked" not in output


def test_a_wrong_ref_is_still_refused_when_it_can_be(runner: CliRunner, fasta: Path) -> None:
    """The premise: with a reference this input is an error, without one it is not."""
    refused = runner.invoke(app, ["resolve", "chr2:1006:T>A", "--reference-fasta", str(fasta)])
    assert refused.exit_code != 0
    assert "reference mismatch" in refused.stderr
    accepted = runner.invoke(app, ["resolve", "chr2:1006:T>A", "--json"])
    assert accepted.exit_code == 0
    assert json.loads(accepted.stdout)["reference_checked"] is False


def test_the_endpoint_reports_it_too() -> None:
    from alleleforge.web.api.app import create_app

    body = (
        TestClient(create_app())
        .post("/api/resolve", json={"variant": "chr7:5530600:A>G", "build": "hg38"})
        .json()
    )
    assert body["reference_checked"] is False
    assert body["reference"] is None
