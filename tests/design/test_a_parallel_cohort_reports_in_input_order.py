"""The same cohort run twice produced two byte-different tables whose rows had moved.

`aforge batch --max-workers 4` recorded results as they finished, so the summary TSV, the
cohort JSON, the HTTP response and the browser's table all came out in *completion* order —
which varies run to run. Three consecutive runs of one six-variant cohort gave three
different row orders, none of them the input's. Serial runs were stable, so the flag that
changed the artifact was a performance flag.

That is a reproducibility failure in a project whose promise is byte-reproducibility, and
the artifact it hits is the one people diff: a cohort table where every row appears to have
changed says nothing about what actually changed.

`_run_windowed` had a reason, and the reason is the interesting part: "the manifest and
resume are set-keyed on `item_id`, so order is not load-bearing". True of the manifest.
True of resume. Those are the two consumers that read results as they arrive, and the
enumeration stopped there — every consumer a *person* reads renders the sequence.

The manifest stays completion-ordered on purpose: it is an append-as-you-go progress log,
and a resumed run reads it as a set. Only the returned report is sorted, and only when the
run is accumulating one — the streaming path holds nothing, which is what keeps its memory
O(max_workers) over a VCF of any size.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.design.cohort import design_many
from alleleforge.genome.reference import ReferenceGenome

_POSITIONS = (100, 300, 500, 700, 900, 1100)


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    import random

    rng = random.Random(3)
    seq = [rng.choice("ACGT") for _ in range(3000)]
    for pos in _POSITIONS:
        seq[pos] = "A"
    path = tmp_path / "multi.fa"
    path.write_text(">chr1\n" + "".join(seq) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def reference(fasta: Path) -> ReferenceGenome:
    return ReferenceGenome(fasta, build="hg38")


def _variants() -> list[str]:
    return [f"chr1:{pos + 1}:A>G" for pos in _POSITIONS]


def _design(fasta: Path, workers: int, **kwargs: object):  # type: ignore[no-untyped-def]
    """Run the cohort the way `aforge batch` does: a fresh reference per worker."""
    reference = ReferenceGenome(fasta, build="hg38")
    extra: dict[str, object] = {"reference": reference}
    if workers > 1:
        # A pyfaidx handle is not thread-safe to share, so the parallel path opens one
        # per worker — the same arrangement the CLI makes.
        extra = {"reference_factory": lambda: ReferenceGenome(fasta, build="hg38")}
    return design_many(
        _variants(),
        max_workers=workers,
        run_offtarget=False,
        **extra,  # type: ignore[arg-type]
        **kwargs,  # type: ignore[arg-type]
    )


def _run(fasta: Path, workers: int, **kwargs: object) -> list[str]:
    return [item.item_id for item in _design(fasta, workers, **kwargs).items]


def test_a_parallel_run_reports_input_order(fasta: Path) -> None:
    assert _run(fasta, 4) == _variants()


def test_parallel_matches_serial(fasta: Path) -> None:
    """The flag is about speed; it must not reorder the table."""
    assert _run(fasta, 4) == _run(fasta, 1)


def test_repeated_parallel_runs_agree(fasta: Path) -> None:
    """Three runs, because the defect showed as three different orders in three runs."""
    orders = {tuple(_run(fasta, 4)) for _ in range(3)}
    assert len(orders) == 1, f"the same cohort produced {len(orders)} different row orders"


def test_the_manifest_is_left_in_completion_order(fasta: Path, tmp_path: Path) -> None:
    """It is a progress log and a resume set — sorting it would be the wrong fix."""
    manifest = tmp_path / "manifest.jsonl"
    report = _design(fasta, 4, manifest_path=manifest)
    lines = [
        line for line in manifest.read_text(encoding="utf-8").splitlines() if '"item_id"' in line
    ]
    assert len(lines) == len(report.items), "every item should be logged as it completes"
    assert [item.item_id for item in report.items] == _variants()


def test_the_streaming_path_still_holds_nothing(fasta: Path) -> None:
    """`on_result` is the bounded-memory path; the ordering must not start buffering."""
    seen: list[str] = []
    report = _design(fasta, 4, on_result=lambda r: seen.append(r.item_id))
    assert report.items == (), "a streaming run must not accumulate a report"
    assert sorted(seen) == sorted(_variants()), "every item still reaches the callback"
