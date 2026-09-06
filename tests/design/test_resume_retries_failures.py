"""A resume must retry what failed, and survive the crash it exists for.

`_read_done_ids` skipped any item the manifest mentioned. Two consequences, both in the
direction that reads as success:

* **A failed item counted as done.** A cohort of 10,000 finishing with 200 errors skipped
  all 10,000 on the next run, reporting `total=0, failed=0` and exiting 0 where the first
  run had exited non-zero. "Re-run until it passes" worked, by doing nothing. The only
  way to retry the 200 was to delete the manifest and lose the 9,800.
* **A truncated final line crashed it.** An append interrupted mid-write leaves exactly
  that, and `json.loads` raised `JSONDecodeError` -- from the one code path whose entire
  purpose is recovering from an interrupted run. A sibling test tolerates *blank* lines,
  so malformed lines had been considered and the wrong case handled.

A malformed line anywhere but the end is still an error: that means a corrupt or
hand-edited manifest, where silently skipping would silently recompute or silently drop.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alleleforge.design.cohort import design_many
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent

OK = "chr2:26:A>G"
#: Asserts a reference base the reference does not carry -- a hard per-item failure.
BAD = "chr2:26:C>G"


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    contig = "T" * 20 + "TTTAAACGTTTTTTTTTTTT" + "TGG" + "T" * 20
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + contig + "\n")
    return ReferenceGenome(fasta, build="hg38")


def _run(reference: ReferenceGenome, manifest: Path) -> object:
    return design_many(
        [OK, BAD], reference=reference, intent=EditIntent.INSTALL, manifest_path=manifest
    )


def test_the_premise_one_item_succeeds_and_one_fails(
    reference: ReferenceGenome, tmp_path: Path
) -> None:
    first = _run(reference, tmp_path / "run.jsonl")
    assert first.succeeded == 1 and first.failed == 1  # type: ignore[attr-defined]


def test_a_resume_retries_the_failure_and_skips_the_success(
    reference: ReferenceGenome, tmp_path: Path
) -> None:
    manifest = tmp_path / "run.jsonl"
    _run(reference, manifest)
    second = _run(reference, manifest)
    assert second.skipped == 1, "the successful item should not be recomputed"  # type: ignore[attr-defined]
    assert second.total == 1, "the failed item should be retried"  # type: ignore[attr-defined]
    assert second.failed == 1  # type: ignore[attr-defined]


def test_a_rerun_does_not_report_a_clean_empty_run(
    reference: ReferenceGenome, tmp_path: Path
) -> None:
    """The shape of the bug: a second run that reports nothing wrong and did nothing."""
    manifest = tmp_path / "run.jsonl"
    _run(reference, manifest)
    second = _run(reference, manifest)
    assert not (second.total == 0 and second.failed == 0), (  # type: ignore[attr-defined]
        "a re-run of a cohort that had failures reported a clean, empty run"
    )


def test_an_interrupted_append_is_recovered_from(
    reference: ReferenceGenome, tmp_path: Path
) -> None:
    manifest = tmp_path / "run.jsonl"
    _run(reference, manifest)
    manifest.write_text(manifest.read_text() + '{"item_id": "chr2:26:A>')

    resumed = _run(reference, manifest)
    assert resumed.skipped == 1  # type: ignore[attr-defined]
    assert resumed.total == 1  # type: ignore[attr-defined]


def test_a_corrupt_line_in_the_middle_is_still_an_error(
    reference: ReferenceGenome, tmp_path: Path
) -> None:
    """Only the *final* line is forgiven; that is the crash signature and nothing else."""
    manifest = tmp_path / "run.jsonl"
    _run(reference, manifest)
    lines = manifest.read_text().splitlines()
    manifest.write_text("\n".join([lines[0], "{not json at all", *lines[1:]]) + "\n")

    with pytest.raises(ValueError, match="line 2 is not valid JSON"):
        _run(reference, manifest)


def test_the_manifest_still_records_both_outcomes(
    reference: ReferenceGenome, tmp_path: Path
) -> None:
    """Retrying a failure must not stop the failure being recorded."""
    manifest = tmp_path / "run.jsonl"
    _run(reference, manifest)
    statuses = [
        json.loads(line)["status"]
        for line in manifest.read_text().splitlines()[1:]
        if "status" in json.loads(line)
    ]
    assert sorted(statuses) == ["error", "ok"]
