"""`--max-workers` was checked for producing the same answers, never for being faster.

The cohort has had a worker pool for many phases, and the guards on it all ask the same
question: are the results identical at one worker and at four? They were, and the flag was
still delivering **1.6x on four threads** — because a PyO3 kernel holds the GIL for its
whole body unless it says otherwise, and 80% of a run is inside one. Four workers were
taking turns to run Rust that never touches the interpreter.

That is fixed in the kernels (see `test_the_scan_releases_the_interpreter`). This file
pins the other half: that the *pool* overlaps items at all. It uses a reference whose
reads block, so the measurement is about scheduling rather than about how fast this
machine happens to be — a serial run of eight blocking items cannot finish in the time
four workers take, whatever the hardware.

The rule the two tests state together: a flag that exists for speed needs a test that
would fail if it stopped delivering it. "Identical results" is the *safety* property, and
a flag can keep it while being inert.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from alleleforge.design.cohort import design_many
from alleleforge.genome.reference import ReferenceGenome

#: Long enough that scheduling dominates, short enough that the test stays quick.
_BLOCK_SECONDS = 0.05


class _SlowReference:
    """A reference whose every read blocks, so the pool's overlap is what is measured.

    `time.sleep` releases the GIL, which is the point: this is a test of the thread pool,
    not of the kernels. If the pool ran items one after another, eight blocking reads
    would cost eight sleeps however many workers were configured.
    """

    def __init__(self, inner: ReferenceGenome) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    # `fetch_result` rather than `fetch`: the design path reads through the richer form
    # (it carries whether the read was clipped), and wrapping the one nobody calls is how
    # a first draft of this file measured nothing at all.
    def fetch_result(self, *args: Any, **kwargs: Any) -> Any:
        time.sleep(_BLOCK_SECONDS)
        return self._inner.fetch_result(*args, **kwargs)


@pytest.fixture
def slow_factory(tmp_path: Path) -> tuple[Callable[[], Any], list[str]]:
    """A factory of blocking references, and a cohort of eight ordinary variants."""
    import random

    rng = random.Random(9)
    sequence = "".join(rng.choice("ACGT") for _ in range(3000))
    fasta = tmp_path / "slow.fa"
    fasta.write_text(">chr1\n" + sequence + "\n")

    variants = []
    for index in range(8):
        position = 1000 + index * 37
        ref_base = sequence[position]
        alt = "A" if ref_base != "A" else "G"
        variants.append(f"chr1:{position + 1}:{ref_base}>{alt}")

    def factory() -> Any:
        return _SlowReference(ReferenceGenome(fasta, build="hg38"))

    return factory, variants


def test_workers_overlap_rather_than_taking_turns(
    slow_factory: tuple[Callable[[], Any], list[str]],
) -> None:
    factory, variants = slow_factory

    start = time.perf_counter()
    serial = design_many(variants, reference=factory(), run_offtarget=False)
    serial_seconds = time.perf_counter() - start

    start = time.perf_counter()
    parallel = design_many(variants, reference_factory=factory, max_workers=4, run_offtarget=False)
    parallel_seconds = time.perf_counter() - start

    assert serial.succeeded == parallel.succeeded == len(variants)
    # A wide margin: four workers on this shape should be near 4x, and anything at or
    # below 1.0 means the pool is not overlapping at all.
    assert serial_seconds / parallel_seconds > 1.8, (
        f"four workers took {parallel_seconds:.2f}s against {serial_seconds:.2f}s "
        "serially: the pool is running items one after another"
    )


def test_the_answers_are_still_the_same(
    slow_factory: tuple[Callable[[], Any], list[str]],
) -> None:
    """The safety property the older guards check, restated here so this file is complete."""
    factory, variants = slow_factory
    serial = design_many(variants, reference=factory(), run_offtarget=False)
    parallel = design_many(variants, reference_factory=factory, max_workers=4, run_offtarget=False)
    by_id = {item.item_id: item.summary for item in parallel.items}
    assert {item.item_id: item.summary for item in serial.items} == by_id
