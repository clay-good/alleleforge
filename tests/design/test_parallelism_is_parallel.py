"""`--max-workers` was checked for producing the same answers, never for being faster.

The cohort has had a worker pool for many phases, and the guards on it all ask the same
question: are the results identical at one worker and at four? They were, and the flag was
still delivering **1.6x on four threads** — because a PyO3 kernel holds the GIL for its
whole body unless it says otherwise, and 80% of a run is inside one. Four workers were
taking turns to run Rust that never touches the interpreter.

That is fixed in the kernels (see `test_the_scan_releases_the_interpreter`). This file
pins the other half: that the *pool* overlaps items at all. It uses a reference whose
reads block and records how many reads are in flight together, so the assertion is about
scheduling rather than a wall-clock ratio that a loaded shared runner can distort.

The rule the two tests state together: a flag that exists for speed needs a test that
would fail if it stopped delivering it. "Identical results" is the *safety* property, and
a flag can keep it while being inert.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from threading import Lock
from time import sleep
from typing import Any

import pytest

from alleleforge.design.cohort import design_many
from alleleforge.genome.reference import ReferenceGenome

#: Long enough that scheduling dominates, short enough that the test stays quick.
_BLOCK_SECONDS = 0.05


class _OverlapProbe:
    """Record how many deliberately blocking reference reads overlap."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.active = 0
        self.peak = 0

    def enter(self) -> None:
        with self._lock:
            self.active += 1
            self.peak = max(self.peak, self.active)

    def leave(self) -> None:
        with self._lock:
            self.active -= 1


class _SlowReference:
    """A reference whose every read blocks, so the pool's overlap is what is measured.

    `time.sleep` releases the GIL, which is the point: this is a test of the thread pool,
    not of the kernels. If the pool ran items one after another, eight blocking reads
    would cost eight sleeps however many workers were configured.
    """

    def __init__(self, inner: ReferenceGenome, probe: _OverlapProbe) -> None:
        self._inner = inner
        self._probe = probe

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    # `fetch_result` rather than `fetch`: the design path reads through the richer form
    # (it carries whether the read was clipped), and wrapping the one nobody calls is how
    # a first draft of this file measured nothing at all.
    def fetch_result(self, *args: Any, **kwargs: Any) -> Any:
        self._probe.enter()
        try:
            sleep(_BLOCK_SECONDS)
            return self._inner.fetch_result(*args, **kwargs)
        finally:
            self._probe.leave()


@pytest.fixture
def slow_factory(tmp_path: Path) -> tuple[Callable[[], Any], list[str], _OverlapProbe]:
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

    probe = _OverlapProbe()

    def factory() -> Any:
        return _SlowReference(ReferenceGenome(fasta, build="hg38"), probe)

    return factory, variants, probe


def test_workers_overlap_rather_than_taking_turns(
    slow_factory: tuple[Callable[[], Any], list[str], _OverlapProbe],
) -> None:
    factory, variants, probe = slow_factory

    parallel = design_many(variants, reference_factory=factory, max_workers=4, run_offtarget=False)

    assert parallel.succeeded == len(variants)
    assert probe.peak > 1, "the worker pool never overlapped two reference reads"


def test_the_answers_are_still_the_same(
    slow_factory: tuple[Callable[[], Any], list[str], _OverlapProbe],
) -> None:
    """The safety property the older guards check, restated here so this file is complete."""
    factory, variants, _probe = slow_factory
    serial = design_many(variants, reference=factory(), run_offtarget=False)
    parallel = design_many(variants, reference_factory=factory, max_workers=4, run_offtarget=False)
    by_id = {item.item_id: item.summary for item in parallel.items}
    assert {item.item_id: item.summary for item in serial.items} == by_id
