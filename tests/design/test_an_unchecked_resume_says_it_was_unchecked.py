"""A resume the manifest could not vouch for looked exactly like a verified one.

`_refuse_a_mismatched_resume` compares the manifest's `_run` header against this run and
refuses a difference — the check that stops a cohort being a silent mixture of two runs.
It compares *what is there*. A manifest written before the header existed has none, and
one written by an older version can be missing a key, and in both cases the guard returned
quietly. That is the input it was written for: the run whose provenance nobody recorded.

Keeping such a manifest resumable is deliberate — making old manifests unusable would
strand real work, and a round said so when the header was introduced. What was missing is
the sentence saying the check did not run: a skipped item reads as work already done, and
`skipped: 14` on a summary is indistinguishable from fourteen verified skips.

So the run says so — in the returned provenance (which the summary TSV, the cohort JSON
and the web batch response all carry), as a `UserWarning` for a Python caller, and on
stderr from `aforge batch`, unconditionally rather than under `--verbose`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from alleleforge.design.cohort import RESUME_UNVERIFIED, design_many
from alleleforge.genome.reference import ReferenceGenome

_SEQ = "ACGTTGCAAGGCTTACCGTA" * 30
_DONE = json.dumps({"item_id": "chr9:31:G>A", "status": "ok"}) + "\n"


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    fasta = tmp_path / "chr9.fa"
    fasta.write_text(">chr9\n" + _SEQ + "\n")
    return ReferenceGenome(fasta, build="hg38")


def _run(reference: ReferenceGenome, manifest: Path, **kwargs: Any) -> Any:
    return design_many(
        ["chr9:31:G>A"], reference=reference, manifest_path=manifest, run_offtarget=False, **kwargs
    )


def test_a_headerless_manifest_is_resumed_and_said_so(
    reference: ReferenceGenome, tmp_path: Path
) -> None:
    manifest = tmp_path / "old.jsonl"
    manifest.write_text(_DONE)
    with pytest.warns(UserWarning, match="no `_run` header"):
        report = _run(reference, manifest)
    assert report.skipped == 1
    assert "unknown" in report.provenance[RESUME_UNVERIFIED]


def test_a_header_missing_a_critical_key_says_which(
    reference: ReferenceGenome, tmp_path: Path
) -> None:
    """An older version's header: present, and silent on the input that decides a run."""
    manifest = tmp_path / "partial.jsonl"
    manifest.write_text(
        json.dumps({"_run": {"seed": 20240501, "intent": "correct"}}) + "\n" + _DONE
    )
    with pytest.warns(UserWarning, match="reference_file"):
        report = _run(reference, manifest)
    assert "reference_build" in report.provenance[RESUME_UNVERIFIED]


def test_a_manifest_this_code_wrote_says_nothing(
    reference: ReferenceGenome, tmp_path: Path
) -> None:
    """The check is not noise: a full header is verified, and stays quiet."""
    manifest = tmp_path / "run.jsonl"
    first = _run(reference, manifest)
    assert RESUME_UNVERIFIED not in first.provenance
    second = _run(reference, manifest)
    assert second.skipped == 1
    assert RESUME_UNVERIFIED not in second.provenance


def test_a_fresh_or_empty_manifest_is_not_a_caveat(
    reference: ReferenceGenome, tmp_path: Path
) -> None:
    """A run killed before its first write, and a path that does not exist yet."""
    for name, contents in (("missing.jsonl", None), ("empty.jsonl", "")):
        manifest = tmp_path / name
        if contents is not None:
            manifest.write_text(contents)
        report = _run(reference, manifest)
        assert RESUME_UNVERIFIED not in report.provenance, name


def test_the_caveat_is_not_a_resume_critical_input(
    reference: ReferenceGenome, tmp_path: Path
) -> None:
    """It describes this run's reading of a manifest, not an input that decides a result.

    Recorded as a critical key it would be compared on the next resume, and a run that
    said "I could not check this" would refuse every later resume of the same manifest.
    """
    from alleleforge.design.cohort import _RESUME_CRITICAL

    assert RESUME_UNVERIFIED not in _RESUME_CRITICAL


def test_the_batch_command_says_it_on_stderr(tmp_path: Path) -> None:
    """The shell the caveat matters most in: a terminal reports `skipped` and no more."""
    from typer.testing import CliRunner

    from alleleforge.cli.main import app

    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    fasta = tmp_path / "prime.fa"
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    inputs = tmp_path / "cohort.txt"
    inputs.write_text("chr2:71:A>C\n")
    manifest = tmp_path / "old.jsonl"
    manifest.write_text(json.dumps({"item_id": "chr2:71:A>C", "status": "ok"}) + "\n")

    result = CliRunner().invoke(
        app,
        [
            "batch",
            str(inputs),
            "--reference-fasta",
            str(fasta),
            "--manifest",
            str(manifest),
            "--no-offtarget",
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    assert "no `_run` header" in (result.stderr or result.output)
