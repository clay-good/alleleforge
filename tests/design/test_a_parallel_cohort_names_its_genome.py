"""A `--max-workers` cohort recorded no run-wide genome, and did not have to.

`design_many` takes a `reference_factory` for parallel runs, because a pyfaidx handle is
not thread-safe to share. The run header treated that as "there is no run-wide reference
to describe" and recorded `None` for the build, `None` for the reference shape and `None`
for the file identity — so a parallel `aforge batch` wrote a cohort summary that could not
say which genome the cohort was screened against, while the identical serial run could.

It also emptied the resume guard. `_refuse_a_mismatched_resume` compares seven inputs; on
a factory-backed run three of them were `None` on both sides, including the two that tell
two same-shaped FASTAs apart — and resuming a cohort against a different genome is the
case that guard exists for.

The factory is opened once before any worker starts anyway, to pre-build the `.fai` so the
workers do not race for it. That open is now what the header is built from: the workers
still get their own handles, and the run says what genome they are handles to.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from alleleforge.design.cohort import design_many
from alleleforge.genome.reference import ReferenceGenome

_SEQ = "ACGTTGCAAGGCTTACCGTA" * 30


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    path = tmp_path / "chr9.fa"
    path.write_text(">chr9\n" + _SEQ + "\n")
    return path


def _parallel(fasta: Path, **kwargs: Any) -> Any:
    return design_many(
        ["chr9:31:G>A"],
        reference_factory=lambda: ReferenceGenome(fasta, build="hg38"),
        max_workers=2,
        run_offtarget=False,
        **kwargs,
    )


def test_the_run_header_names_the_genome(fasta: Path) -> None:
    provenance = _parallel(fasta).provenance
    assert provenance["reference_build"] == "hg38"
    assert provenance["reference"]["contigs"] == 1
    assert provenance["reference_file"] is not None


def test_the_resume_guard_can_tell_two_genomes_apart(fasta: Path, tmp_path: Path) -> None:
    """The three keys that were `None` on both sides are what this guard compares."""
    manifest = tmp_path / "run.jsonl"
    _parallel(fasta, manifest_path=manifest)
    other = tmp_path / "other.fa"
    other.write_text(">chr9\n" + _SEQ + "\n")  # same shape, different file
    with pytest.raises(ValueError, match="reference_file"):
        design_many(
            ["chr9:31:G>A"],
            reference_factory=lambda: ReferenceGenome(other, build="hg38"),
            max_workers=2,
            run_offtarget=False,
            manifest_path=manifest,
        )


def test_a_different_build_is_refused_too(fasta: Path, tmp_path: Path) -> None:
    manifest = tmp_path / "build.jsonl"
    _parallel(fasta, manifest_path=manifest)
    with pytest.raises(ValueError, match="reference_build"):
        design_many(
            ["chr9:31:G>A"],
            reference_factory=lambda: ReferenceGenome(fasta, build="mm39"),
            max_workers=2,
            run_offtarget=False,
            manifest_path=manifest,
        )


def test_the_manifest_header_carries_it(fasta: Path, tmp_path: Path) -> None:
    """The header is the artifact a reader consults months later."""
    manifest = tmp_path / "header.jsonl"
    _parallel(fasta, manifest_path=manifest)
    header = json.loads(manifest.read_text().splitlines()[0])["_run"]
    assert header["reference_build"] == "hg38"
    assert header["reference"]["bases"] == len(_SEQ)
