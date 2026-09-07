"""No command-line user could reach the variant-consequence annotator.

`design()` takes an `effect` predictor, annotates the menu with what the variant is
predicted to do, and raises a caution when the intent is to *correct* a variant whose
predicted impact is a modifier — "confirm this is the change you mean to make". A
library caller got all of that. A command-line user could not get any of it: no
command took a flag for it, and `aforge design` resolves the variant itself, so even
passing the predictor down to `design()` would have been dropped on the floor (see
`tests/design/test_a_resolver_argument_that_cannot_take_is_refused`).

`--vep` closes it on `resolve`, `design` and `batch`, wired at the point where each
command actually resolves. The flag is the consent: what the predictor's own gate
protects is *outbound* disclosure — the variant, possibly from a patient VCF, goes to
a third-party public server — so the help text says that at the prompt.

The tests below never touch the network: they patch the predictor's `predict`, which
is what the flag constructs, and assert the consequence reaches the output.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app
from alleleforge.variant.effect import Consequence, Impact, VariantEffect, VepRestPredictor

runner = CliRunner()

_CONTIG = "T" * 20 + "ACGTAACGTTACGTAACGTT" + "TGG" + "T" * 20
_EFFECT = VariantEffect(
    consequence=Consequence.SPLICE_DONOR,
    impact=Impact.HIGH,
    gene="TESTG",
    transcript="ENST00000000001",
)


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    path = tmp_path / "ref.fa"
    path.write_text(f">chr2\n{_CONTIG}\n", encoding="utf-8")
    return path


@pytest.fixture
def offline_vep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer every VEP lookup locally, so the flag is exercised without a request."""
    monkeypatch.setattr(
        VepRestPredictor,
        "predict",
        lambda self, variant, *, transcript="MANE_SELECT": _EFFECT,
    )


def _variant() -> str:
    return f"chr2:26:{_CONTIG[25]}>G"


def test_resolve_reports_the_consequence_when_asked(fasta: Path, offline_vep: None) -> None:
    result = runner.invoke(
        app,
        ["resolve", _variant(), "--reference-fasta", str(fasta), "--vep", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["consequence"] == "splice_donor_variant"
    assert payload["impact"] == "HIGH"
    assert payload["gene"] == "TESTG"
    assert payload["consequence_checked"] is True


def test_an_unasked_consequence_is_not_reported_as_absent(fasta: Path) -> None:
    """A null consequence must be readable as "nobody asked", not "VEP found nothing"."""
    result = runner.invoke(app, ["resolve", _variant(), "--reference-fasta", str(fasta), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["consequence"] is None
    assert payload["consequence_checked"] is False


def test_design_carries_the_consequence_onto_the_menu(fasta: Path, offline_vep: None) -> None:
    result = runner.invoke(
        app,
        [
            "design",
            _variant(),
            "--reference-fasta",
            str(fasta),
            "--vep",
            "--no-offtarget",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "splice donor variant" in result.stdout, (
        "the menu must state the consequence the user paid a disclosure for"
    )
    assert "TESTG" in result.stdout, "the menu must name the gene the consequence is on"


def test_the_flag_states_what_leaves_the_machine() -> None:
    """The gate is about outbound data, so the help must say so, not just "network"."""
    for command in ("resolve", "design", "batch"):
        result = runner.invoke(app, [command, "--help"])
        assert result.exit_code == 0, result.output
        help_text = " ".join(result.stdout.split())
        assert "--vep" in help_text, f"{command} does not offer --vep"
        assert "third-party" in help_text, f"{command}'s --vep does not name the recipient"
