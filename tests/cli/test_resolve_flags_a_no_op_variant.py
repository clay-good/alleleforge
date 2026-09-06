"""`aforge resolve` must say when the variant it normalized changes nothing.

A variant whose reference and alternate alleles are equal is not a variant. The
design path already refuses one, by name and with a non-zero exit:

    prime: eligible but no actionable candidate enumerated — the requested edit does
    not change the sequence (the reference and desired alleles are identical), so
    there is nothing to write

`resolve` — the documented debugging aid, the command whose whole job is to tell a
caller what their input means — reported it as an ordinary SNV:

    chr1:999:A>A  [snv, build hg38, from coordinates]

`variant_class` is computed from the allele *lengths*, so a one-base ref and a
one-base alt is an `snv` whether or not they differ, and the JSON payload said `snv`
to a machine consumer too. Neither is wrong exactly; both are silent about the one
thing that makes this input useless.

It is deliberately **not** an error. A reference call (`0/0`) in a VCF is a legitimate
row, `aforge batch` reads VCFs, and refusing here would fail a cohort on rows the
design path currently declines gracefully. Say it, do not refuse it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _resolve(runner: CliRunner, variant: str, *extra: str) -> tuple[str, dict]:
    human = runner.invoke(app, ["resolve", variant, *extra])
    assert human.exit_code == 0, human.output + human.stderr
    as_json = runner.invoke(app, ["resolve", variant, "--json", *extra])
    assert as_json.exit_code == 0, as_json.output
    return human.output, json.loads(as_json.stdout)


def test_a_no_op_is_flagged_in_both_forms(runner: CliRunner) -> None:
    human, payload = _resolve(runner, "chr1:1000:A>A")
    assert "does not change the sequence" in human
    assert payload["changes_the_sequence"] is False


def test_a_real_variant_is_not_flagged(runner: CliRunner) -> None:
    human, payload = _resolve(runner, "chr1:1000:A>C")
    assert "does not change the sequence" not in human
    assert payload["changes_the_sequence"] is True


@pytest.mark.parametrize(
    "variant, changes",
    [
        ("chr1:1000:A>A", False),
        ("chr1:1000:AT>AT", False),
        ("chr1:1000:A>C", True),
        ("chr1:1000:AT>A", True),
        ("chr1:1000:A>AT", True),
    ],
)
def test_the_flag_tracks_the_alleles(runner: CliRunner, variant: str, changes: bool) -> None:
    _, payload = _resolve(runner, variant)
    assert payload["changes_the_sequence"] is changes


def test_it_is_reported_not_refused(runner: CliRunner) -> None:
    """A reference call is a legitimate VCF row; a cohort must not fail on one."""
    result = runner.invoke(app, ["resolve", "chr1:1000:A>A"])
    assert result.exit_code == 0


def test_the_web_resolve_says_it_too(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The library is the source of truth; both shells must report the same fact."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from alleleforge.web.api.app import create_app

    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    monkeypatch.setenv("ALLELEFORGE_REFERENCE_FASTA", str(fasta))
    client = TestClient(create_app())

    assert (
        client.post("/api/resolve", json={"variant": "chr2:71:A>A"}).json()["changes_the_sequence"]
        is False
    )
    assert (
        client.post("/api/resolve", json={"variant": "chr2:71:A>C"}).json()["changes_the_sequence"]
        is True
    )
