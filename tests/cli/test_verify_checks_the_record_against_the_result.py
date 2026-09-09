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

Emptying the list is not the only way to lose the models that matter, and the check that
caught it only caught that. A block naming a model for some *other* chemistry looks
populated: deleting the two prime cards from a prime-only menu and leaving the unrelated
base-editor one behind reported "1 model(s)" and "complete and consistent", with nothing
named against a single number in the file. A checkpoint is tagged with the chemistry it
scored and every candidate states its own, so the finer question is answerable too.

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
from alleleforge.design.base_editor import base_editor_model_checkpoints
from alleleforge.design.cas9 import cas9_model_checkpoints
from alleleforge.design.designer import model_chemistry_group
from alleleforge.design.prime import prime_model_checkpoints
from alleleforge.offtarget.scoring import APPROX_CFD_MATRIX_ID, PUBLISHED_CFD_MATRIX_ID
from alleleforge.types.edit import Chemistry


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


# --- the model half, one level finer: a populated block that names nothing relevant ---


def _base_editor_row() -> dict[str, object]:
    """The real card the base vertical stamps, as it appears in a provenance block.

    Synthesized rather than taken from a run: the point of the tests below is a block
    that *looks* populated while naming nothing for the candidates, and which unrelated
    model a given variant happens to record is not a property worth depending on.
    """
    (checkpoint,) = base_editor_model_checkpoints()
    assert checkpoint.chemistry == Chemistry.BASE_ABE.value
    return checkpoint.model_dump(mode="json")


def test_dropping_only_the_models_that_scored_it_is_refused(report: Path, tmp_path: Path) -> None:
    payload = json.loads(report.read_text())
    ranked = {c["chemistry"] for c in payload["candidates"]}
    assert ranked == {Chemistry.PRIME.value}, ranked
    payload["provenance"]["models"] = [
        m for m in payload["provenance"]["models"] if m["chemistry"] != Chemistry.PRIME.value
    ] + [_base_editor_row()]
    tampered = tmp_path / "no-prime-model.json"
    tampered.write_text(json.dumps(payload))

    code, output = _verify(tampered)
    assert code != ExitCode.OK, output
    assert "complete and consistent" not in output
    assert "names no prime model" in output, output


def test_a_base_editor_candidate_is_covered_by_the_card_the_vertical_stamps(
    report: Path, tmp_path: Path
) -> None:
    """The negative case, and the reason the check groups instead of comparing labels.

    The base vertical is one call covering ABE and CBE, and stamps a single card tagged
    `base_abe`. Real runs do rank `base_cbe` candidates against exactly that card — a
    159-run sweep produced sixteen of them — so a checker comparing the two labels
    directly would refuse genuine output.
    """
    assert Chemistry.BASE_CBE in model_chemistry_group(Chemistry.BASE_ABE)
    payload = json.loads(report.read_text())
    assert payload["candidates"], "need a candidate to relabel"
    for candidate in payload["candidates"]:
        candidate["chemistry"] = Chemistry.BASE_CBE.value
    payload["provenance"]["models"] = [_base_editor_row()]
    cbe = tmp_path / "cbe.json"
    cbe.write_text(json.dumps(payload))

    code, output = _verify(cbe)
    assert code == ExitCode.OK, output


def test_the_grouping_matches_the_checkpoints_the_producer_stamps() -> None:
    """`verify` reads the grouping off `designer`; this pins that it is the real one.

    Every chemistry the designer can run must stamp checkpoints tagged inside its own
    group. If a vertical were retagged, or a new chemistry added whose card carries a
    different tag, the cross-check above would start refusing real output — so the
    correspondence is checked rather than assumed.
    """
    for chemistry, checkpoints in (
        (Chemistry.CAS9_NUCLEASE, cas9_model_checkpoints()),
        (Chemistry.PRIME, prime_model_checkpoints()),
        (Chemistry.BASE_ABE, base_editor_model_checkpoints()),
        (Chemistry.BASE_CBE, base_editor_model_checkpoints()),
    ):
        group = {c.value for c in model_chemistry_group(chemistry)}
        assert checkpoints, f"{chemistry.value} stamps no checkpoint"
        tags = {ck.chemistry for ck in checkpoints}
        assert tags <= group, f"{chemistry.value}: {tags} outside {group}"


def test_an_emptied_list_still_gets_the_message_written_for_it(
    report: Path, tmp_path: Path
) -> None:
    """Both checks answer "what produced these numbers"; only one should speak at a time."""
    payload = json.loads(report.read_text())
    payload["provenance"]["models"] = []
    tampered = tmp_path / "empty-models.json"
    tampered.write_text(json.dumps(payload))

    code, output = _verify(tampered)
    assert code != ExitCode.OK, output
    assert "names no model" in output
    assert "names no prime model" not in output, output
