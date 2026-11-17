"""Two lines decide how many times a cohort opens the genome, and neither was observed.

`design_many` takes a `reference_factory` rather than a `ReferenceGenome` for the
parallel path, because a pyfaidx handle is not thread-safe to share. Two statements turn
that factory into "once per worker, plus one to describe the run", and a
statement-deletion sweep removed each with the whole suite green:

* ``tl.ref = ref`` caches the handle on the thread-local. Without it the factory runs
  **once per item** — a cohort of five hundred variants opens, indexes and closes the
  reference five hundred times, and every result is still correct, which is exactly why
  nothing noticed.
* ``probe.close()`` closes the extra handle opened up front to read the build label and
  contig digest for the run header. Without it that handle stays open for the whole
  run.

Both are about what the run *costs*, not what it answers, and a suite that checks
answers cannot see either. Counted here instead: the factory is wrapped so every call
and every close is recorded.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from alleleforge.design.cohort import design_many
from alleleforge.genome.reference import ReferenceGenome


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    rng = random.Random(5)
    path = tmp_path / "ref.fa"
    path.write_text(">chr2\n" + "".join(rng.choice("ACGT") for _ in range(3_000)) + "\n")
    return path


class _CountingFactory:
    """A `reference_factory` that records every handle it hands out."""

    def __init__(self, fasta: Path) -> None:
        self._fasta = fasta
        self.opened: list[ReferenceGenome] = []
        self.closed: list[ReferenceGenome] = []

    def __call__(self) -> ReferenceGenome:
        reference = ReferenceGenome(self._fasta, build="hg38")
        close = reference.close

        def _record() -> None:
            self.closed.append(reference)
            close()

        reference.close = _record  # type: ignore[method-assign]
        self.opened.append(reference)
        return reference


_ITEMS = [f"chr2:{pos}:{{ref}}>A" for pos in (1200, 1300, 1400, 1500, 1600, 1700)]


def _variants(fasta: Path) -> list[str]:
    bases = "".join(fasta.read_text().split("\n")[1:])
    out = []
    for item in _ITEMS:
        pos = int(item.split(":")[1])
        ref = bases[pos - 1]
        out.append(item.format(ref=ref).replace(">A", ">C" if ref == "A" else ">A"))
    return out


def test_a_sequential_run_opens_one_handle_to_describe_itself(fasta: Path) -> None:
    """The probe: one extra open, and it must not stay open."""
    factory = _CountingFactory(fasta)
    report = design_many(
        _variants(fasta), reference_factory=factory, run_offtarget=False, manifest_path=None
    )
    assert report.total == len(_ITEMS)
    assert factory.opened, "the factory was never called"
    assert factory.closed, "the handle opened to describe the run was never closed"


@pytest.mark.parametrize("workers", [1, 2])
def test_a_worker_reuses_its_reference_rather_than_reopening_it(fasta: Path, workers: int) -> None:
    """One handle per worker, plus the probe — not one per item."""
    factory = _CountingFactory(fasta)
    report = design_many(
        _variants(fasta),
        reference_factory=factory,
        max_workers=workers,
        run_offtarget=False,
        manifest_path=None,
    )
    assert report.total == len(_ITEMS)
    assert len(factory.opened) <= workers + 1, (
        f"{len(factory.opened)} handles for {len(_ITEMS)} items on {workers} worker(s): "
        "the reference is being reopened per item"
    )
