"""`verify` accepted a provenance record that named nothing, beside a page of numbers.

The command exists to make provenance "a checkable contract, not a record". Every check
it ran was verifiable from the provenance block *by itself*: a version string, a config
snapshot, and a name/version on each entry that is listed. Nothing looked at the artifact
the block is attached to. So emptying `models` — one edit, in the obvious place, on a
report full of efficiency predictions in the same file — left it reporting

    provenance: aforge 0.1.0.dev0, seed 20240501, 0 model(s), 0 dataset(s)
    verified: provenance is complete and consistent

A prediction implies a scorer ran, and provenance's whole job is naming what produced the
numbers. A result carrying predictions and naming no model is the state this command is
for. The bare `.provenance.json` sidecar carries no such evidence and is unaffected — it
cannot be cross-checked, and pretending otherwise would refuse three of the four output
formats.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    path = tmp_path / "prime.fa"
    path.write_text(">chr2\n" + "".join(seq) + "\n")
    return path


@pytest.fixture
def report(fasta: Path, tmp_path: Path) -> Path:
    out = tmp_path / "report.json"
    result = CliRunner().invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(fasta),
            "--intent",
            "install",
            "--max-per-chemistry",
            "2",
            "--no-offtarget",
            "--format",
            "json",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.stderr
    return out


def _verify(path: Path) -> tuple[int, str]:
    result = CliRunner().invoke(app, ["verify", str(path)])
    return result.exit_code, result.output + result.stderr


def test_the_fixture_names_models_and_carries_predictions(report: Path) -> None:
    """Both halves of the cross-check must be live, or it proves nothing."""
    payload = json.loads(report.read_text())
    assert payload["provenance"]["models"], "the run recorded no model"
    assert any(c.get("efficiency") for c in payload["candidates"]), "no predictions"


def test_an_untouched_report_verifies(report: Path) -> None:
    code, output = _verify(report)
    assert code == ExitCode.OK, output
    assert "complete and consistent" in output


def test_emptying_the_model_list_is_refused(report: Path, tmp_path: Path) -> None:
    payload = json.loads(report.read_text())
    payload["provenance"]["models"] = []
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(payload))

    code, output = _verify(tampered)
    assert code != ExitCode.OK, output
    assert "complete and consistent" not in output
    assert "names no model" in output, output


def test_a_bare_sidecar_with_no_models_is_still_accepted(report: Path, tmp_path: Path) -> None:
    """It has no artifact to be inconsistent with; refusing it would be a guess."""
    provenance = json.loads(report.read_text())["provenance"]
    provenance["models"] = []
    sidecar = tmp_path / "bare.provenance.json"
    sidecar.write_text(json.dumps(provenance))

    code, output = _verify(sidecar)
    assert code == ExitCode.OK, output


def test_a_report_with_no_candidates_and_no_models_is_accepted(
    report: Path, tmp_path: Path
) -> None:
    """Nothing was predicted, so nothing needs a model named against it."""
    payload = json.loads(report.read_text())
    payload["candidates"] = []
    payload["provenance"]["models"] = []
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps(payload))

    code, output = _verify(empty)
    assert code == ExitCode.OK, output
