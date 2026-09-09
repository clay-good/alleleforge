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

The dataset half of the same sentence had the same hole, and a worse consequence. The
help says `verify` "confirms the block names every model *and dataset* the result used",
and every candidate says which scoring matrix produced its off-target numbers — so the
evidence was there. Deleting the `doench-2016-cfd` row still verified clean, *including*
under `--cache-dir`, where the matrix is the one artifact that is actually re-hashed: no
row, nothing to re-hash, "verified". The tamper contract was defeated by deleting a row
instead of editing bytes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app
from alleleforge.data.registry import DEFAULT_REGISTRY
from alleleforge.offtarget.scoring import APPROX_CFD_MATRIX_ID, PUBLISHED_CFD_MATRIX_ID


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


# --- the dataset half: the scoring matrix a result names must be in provenance ---


@pytest.fixture
def scored_report(fasta: Path, tmp_path: Path) -> Path:
    """As `report`, but with the off-target search on, so a matrix scored it.

    `report` passes `--no-offtarget` — the fast path for the model half — and a run
    that never scored an off-target names no matrix at all. This half of the contract
    needs a run that did.
    """
    out = tmp_path / "scored.json"
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
            "--format",
            "json",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.stderr
    return out


def test_the_scored_fixture_names_a_matrix_and_records_it(scored_report: Path) -> None:
    """Both halves of this cross-check must be live too, or it proves nothing."""
    payload = json.loads(scored_report.read_text())
    assert any(c.get("offtarget_matrix") for c in payload["candidates"]), (
        "no candidate names the matrix that scored it"
    )
    assert any(d["name"] == PUBLISHED_CFD_MATRIX_ID for d in payload["provenance"]["datasets"]), (
        "the run did not record the matrix it scored with"
    )


def test_an_untouched_scored_report_verifies(scored_report: Path) -> None:
    code, output = _verify(scored_report)
    assert code == ExitCode.OK, output
    assert "complete and consistent" in output


def test_dropping_the_scoring_matrix_is_refused(scored_report: Path, tmp_path: Path) -> None:
    payload = json.loads(scored_report.read_text())
    payload["provenance"]["datasets"] = [
        d for d in payload["provenance"]["datasets"] if d["name"] != PUBLISHED_CFD_MATRIX_ID
    ]
    tampered = tmp_path / "no-matrix.json"
    tampered.write_text(json.dumps(payload))

    code, output = _verify(tampered)
    assert code != ExitCode.OK, output
    assert "complete and consistent" not in output
    assert PUBLISHED_CFD_MATRIX_ID in output, output


def test_dropping_the_matrix_does_not_pass_under_cache_dir_either(
    scored_report: Path, tmp_path: Path
) -> None:
    """The regression that made this worth fixing: the deleted row was the *only* one
    `--cache-dir` re-hashes, so the byte check quietly had nothing to do and said so in
    a NOTE while still exiting zero."""
    payload = json.loads(scored_report.read_text())
    payload["provenance"]["datasets"] = []
    tampered = tmp_path / "no-datasets.json"
    tampered.write_text(json.dumps(payload))

    result = CliRunner().invoke(
        app, ["verify", str(tampered), "--cache-dir", str(tmp_path / "cache")]
    )
    assert result.exit_code != ExitCode.OK, result.output + result.stderr


def test_the_approximation_is_not_demanded_of_provenance(
    scored_report: Path, tmp_path: Path
) -> None:
    """The negative case, and the reason this matches by registry membership.

    The length-relative approximation is code, not data: it has no bytes to pin and the
    designer deliberately does not record it (`_collect_datasets`: "only matrices the
    registry knows are recorded"). A check that demanded every named matrix appear in
    `datasets` would refuse every result that fell back even once.
    """
    assert APPROX_CFD_MATRIX_ID not in DEFAULT_REGISTRY
    payload = json.loads(scored_report.read_text())
    for candidate in payload["candidates"]:
        if candidate.get("offtarget_matrix") is not None:
            candidate["offtarget_matrix"] = APPROX_CFD_MATRIX_ID
    payload["provenance"]["datasets"] = []
    approximated = tmp_path / "approximated.json"
    approximated.write_text(json.dumps(payload))

    code, output = _verify(approximated)
    assert code == ExitCode.OK, output


def test_a_mixed_matrix_label_still_demands_the_published_half(
    scored_report: Path, tmp_path: Path
) -> None:
    """A table that fell back on some sites reads ``"published + approximation"``. The
    published half was still read, so it still has to be named."""
    payload = json.loads(scored_report.read_text())
    labelled = False
    for candidate in payload["candidates"]:
        if candidate.get("offtarget_matrix") is not None:
            candidate["offtarget_matrix"] = f"{PUBLISHED_CFD_MATRIX_ID} + {APPROX_CFD_MATRIX_ID}"
            labelled = True
    assert labelled
    payload["provenance"]["datasets"] = []
    mixed = tmp_path / "mixed.json"
    mixed.write_text(json.dumps(payload))

    code, output = _verify(mixed)
    assert code != ExitCode.OK, output
    assert PUBLISHED_CFD_MATRIX_ID in output, output
