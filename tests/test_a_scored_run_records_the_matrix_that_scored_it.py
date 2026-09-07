"""Every specificity on the page came out of a dataset the run did not record.

`aforge design --region ...` scored each candidate with the vendored Doench 2016 CFD
matrix and said so on every row — `matrix doench-2016-cfd`, with the citation. Its
provenance said:

    provenance: aforge 0.1.0.dev0, seed 20240501, 2 model(s), 0 dataset(s)

The matrix is a registered dataset with a pinned sha256, and it is the *only* one whose
bytes actually ship. Two consequences, and the second is the one that matters. The
provenance footer names "the datasets and tools a run consumed" and named none. And
`verify --cache-dir` re-hashes `provenance.datasets`, so the tamper contract — the
mechanism that turns provenance from a record into a checkable claim — did not cover the
file that produced every safety number on the result.

Recording it exposed a second defect immediately: `verify` looked for it in the cache and
reported `not-cached`. `bundled` said the bytes ship and nothing said *where*, so the one
dataset that can always be hashed was the one reported unavailable.

The matrices are read off the *results*, not off the scorer's configuration: a fixed
published matrix falls back to the length-relative approximation per hit, and the
approximation is code with no bytes to pin.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app
from alleleforge.data.registry import DEFAULT_REGISTRY, DatasetDescriptor
from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.scoring import (
    APPROX_CFD_MATRIX_ID,
    CFD_MATRIX_FILE,
    PUBLISHED_CFD_MATRIX_ID,
)
from alleleforge.types.edit import EditIntent


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    rng = random.Random(7)
    seq = [rng.choice("ACGT") for _ in range(3_000)]
    seq[1000:1023] = list("ACCTGAAGACTTACGCATAC" + "TGG")
    path = tmp_path / "ref.fa"
    path.write_text(">chr1\n" + "".join(seq) + "\n")
    return path


def _menu(fasta: Path, *, run_offtarget: bool) -> object:
    return design(
        "chr1:1018:T>A",
        reference=ReferenceGenome(fasta, build="hg38"),
        run_offtarget=run_offtarget,
        intent=EditIntent.KNOCK_OUT,
    )


def test_a_searched_run_names_the_matrix_it_scored_with(fasta: Path) -> None:
    menu = _menu(fasta, run_offtarget=True)
    assert any(c.offtarget is not None for c in menu.candidates), "nothing was searched"
    names = {d.name for d in menu.provenance.datasets}
    assert PUBLISHED_CFD_MATRIX_ID in names, names


def test_the_recorded_matrix_carries_its_pinned_hash(fasta: Path) -> None:
    """A dataset with no sha256 cannot be re-hashed, so recording it would prove nothing."""
    recorded = next(
        d
        for d in _menu(fasta, run_offtarget=True).provenance.datasets
        if d.name == PUBLISHED_CFD_MATRIX_ID
    )
    assert recorded.sha256 == DEFAULT_REGISTRY.get(PUBLISHED_CFD_MATRIX_ID).sha256
    assert recorded.citation


def test_an_unsearched_run_records_no_matrix(fasta: Path) -> None:
    """Nothing was scored, so nothing was consumed — the R278 distinction."""
    names = {d.name for d in _menu(fasta, run_offtarget=False).provenance.datasets}
    assert PUBLISHED_CFD_MATRIX_ID not in names, names


def test_the_approximation_is_not_recorded_as_a_dataset() -> None:
    """It is code with no bytes to pin; it is already named per site and per candidate."""
    assert APPROX_CFD_MATRIX_ID not in DEFAULT_REGISTRY


def test_the_registry_and_the_scorer_point_at_one_file() -> None:
    """Two paths to the same bytes are two paths that drift."""
    descriptor = DEFAULT_REGISTRY.get(PUBLISHED_CFD_MATRIX_ID)
    assert descriptor.bundled_file() == CFD_MATRIX_FILE
    assert CFD_MATRIX_FILE.is_file()


def test_verify_rehashes_the_bundled_matrix(fasta: Path, tmp_path: Path) -> None:
    """Recording it is only worth anything if the tamper check can reach the bytes."""
    out = tmp_path / "menu.json"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "design",
            "chr1:1018:T>A",
            "--reference-fasta",
            str(fasta),
            "--intent",
            "knock_out",
            "--region",
            "chr1:0-3000",
            "--format",
            "json",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.stderr

    empty_cache = tmp_path / "cache"
    empty_cache.mkdir()
    verified = runner.invoke(app, ["verify", str(out), "--cache-dir", str(empty_cache)])
    assert verified.exit_code == ExitCode.OK, verified.stderr
    output = verified.output + verified.stderr
    assert f"{PUBLISHED_CFD_MATRIX_ID}.2016: ok" in output, output
    assert "nothing was re-hashed" not in output, output


def test_verify_catches_a_tampered_bundled_matrix(
    fasta: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The point of recording it: altered weights must not verify.

    The bytes are read from the installed package, so the tamper is staged by pointing
    the descriptor's bundled path at a modified copy — the same file the scorer would
    load, with one weight changed.
    """
    out = tmp_path / "menu.json"
    runner = CliRunner()
    designed = runner.invoke(
        app,
        [
            "design",
            "chr1:1018:T>A",
            "--reference-fasta",
            str(fasta),
            "--intent",
            "knock_out",
            "--region",
            "chr1:0-3000",
            "--format",
            "json",
            "--out",
            str(out),
        ],
    )
    assert designed.exit_code == 0, designed.stderr

    tampered = tmp_path / "cfd_matrix.json"
    tampered.write_bytes(CFD_MATRIX_FILE.read_bytes().replace(b'"rU:dT,1"', b'"rU:dT,2"', 1))
    assert tampered.read_bytes() != CFD_MATRIX_FILE.read_bytes(), "the edit did not apply"
    # The descriptor is frozen, so the method is patched on the class and keyed by name:
    # only the matrix under test is redirected, and every other bundled dataset keeps
    # resolving normally.
    original = DatasetDescriptor.bundled_file
    monkeypatch.setattr(
        DatasetDescriptor,
        "bundled_file",
        lambda self: tampered if self.name == PUBLISHED_CFD_MATRIX_ID else original(self),
    )

    result = runner.invoke(app, ["verify", str(out), "--cache-dir", str(tmp_path / "cache")])
    assert result.exit_code == ExitCode.UNAVAILABLE, result.output + result.stderr
    assert "MISMATCH" in result.output + result.stderr
