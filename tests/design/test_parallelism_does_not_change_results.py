"""A cohort's artifacts must not depend on how many threads produced them.

`design_many` already has a parallel-vs-sequential equivalence test, and it compares the
in-memory results: per-item status and summary. It does not use `output_dir`, so the
files on disk -- the actual deliverable of a batch run, and the surface a concurrency
defect had been living on -- were outside it.

That defect was real: `_atomic_write_text` named its temp file with the process id, which
every worker thread shares, so two items resolving to the same output path wrote and
renamed one file. Fixed by making the name unique per call.

Reaching it end to end needs a cohort with a **repeated** item -- three distinct variants
never collide on an output path, and a first version of this file used three distinct
variants and did not catch the old bug at all. A variant appearing twice in a VCF is
ordinary, so the duplicate case is the one that exercises the fix.

Worker count is a performance knob. Nothing a caller reads should be able to tell what it
was set to.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from alleleforge.design.cohort import design_many
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent

from .test_cohort import NEW_ITEM, OK_1, OK_2, _write_fasta

COHORT = [OK_1, OK_2, NEW_ITEM]


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    path = tmp_path / "cohort.fa"
    _write_fasta(path)
    return path


@pytest.fixture
def reference(fasta: Path) -> ReferenceGenome:
    return ReferenceGenome(fasta, build="hg38")


@pytest.fixture
def ref_factory(fasta: Path) -> Callable[[], ReferenceGenome]:
    """A fresh handle per worker: a pyfaidx handle is not thread-safe to share."""
    return lambda: ReferenceGenome(fasta, build="hg38")


def _menus(output_dir: Path) -> dict[str, object]:
    """Return ``{filename: candidates}`` for every menu written."""
    return {
        path.name: json.loads(path.read_text())["candidates"]
        for path in sorted(output_dir.iterdir())
    }


@pytest.fixture
def written(
    tmp_path: Path, reference: ReferenceGenome, ref_factory: Callable[[], ReferenceGenome]
) -> tuple[dict[str, object], dict[str, object]]:
    """Run the same cohort sequentially and on three workers, returning both outputs."""
    sequential, parallel = tmp_path / "seq", tmp_path / "par"
    design_many(
        COHORT,
        reference=reference,
        intent=EditIntent.INSTALL,
        output_dir=sequential,
        manifest_path=tmp_path / "seq.jsonl",
    )
    design_many(
        COHORT,
        reference_factory=ref_factory,
        intent=EditIntent.INSTALL,
        output_dir=parallel,
        manifest_path=tmp_path / "par.jsonl",
        max_workers=3,
    )
    return _menus(sequential), _menus(parallel)


def test_the_premise_menus_were_actually_written(
    written: tuple[dict[str, object], dict[str, object]],
) -> None:
    """A floor: comparing two empty directories proves nothing."""
    sequential, _ = written
    assert len(sequential) == len(COHORT), sequential
    assert all(candidates for candidates in sequential.values()), "a menu came back empty"


def test_the_same_files_are_written(
    written: tuple[dict[str, object], dict[str, object]],
) -> None:
    sequential, parallel = written
    assert sorted(sequential) == sorted(parallel)


def test_every_menu_is_identical(
    written: tuple[dict[str, object], dict[str, object]],
) -> None:
    """Compares the science, not the provenance: only the timestamp may differ."""
    sequential, parallel = written
    for name, candidates in sequential.items():
        assert parallel[name] == candidates, f"{name} differs between 1 and 3 workers"


def test_every_menu_is_valid_json_of_a_whole_run(
    tmp_path: Path, ref_factory: Callable[[], ReferenceGenome]
) -> None:
    """The torn-write failure mode: two payloads mixed in one file do not parse.

    Asserted separately from equality because a mixture can happen to be equal-length
    and would still be caught here, and because this is the check that would survive
    the menus themselves changing.
    """
    output_dir = tmp_path / "out"
    design_many(
        COHORT,
        reference_factory=ref_factory,
        intent=EditIntent.INSTALL,
        output_dir=output_dir,
        max_workers=3,
    )
    for path in output_dir.iterdir():
        payload = json.loads(path.read_text())  # raises on a torn write
        assert "candidates" in payload and "provenance" in payload, path.name
    assert not [p for p in output_dir.iterdir() if p.name.endswith(".tmp")]


def test_a_repeated_item_does_not_corrupt_its_output(
    tmp_path: Path, ref_factory: Callable[[], ReferenceGenome]
) -> None:
    """The case that actually reaches the shared-temp-file defect.

    Two items with the same id resolve to the same output path, so the two workers
    write and rename one file. With a process-scoped temp name they share it: the first
    `os.replace` moves it away and the second raises FileNotFoundError, recorded against
    an item whose data was fine. Distinct ids never collide, which is why a cohort of
    three different variants passes either way.
    """
    output_dir = tmp_path / "out"
    repeated = [OK_1, OK_1, OK_1, OK_2]

    report = design_many(
        repeated,
        reference_factory=ref_factory,
        intent=EditIntent.INSTALL,
        output_dir=output_dir,
        max_workers=4,
    )

    assert report.failed == 0, [item.error for item in report.items if item.error]
    written = sorted(output_dir.iterdir())
    assert len(written) == 2, f"one file per distinct id: {[p.name for p in written]}"
    for path in written:
        payload = json.loads(path.read_text())  # raises on a torn write
        assert payload["candidates"], path.name
