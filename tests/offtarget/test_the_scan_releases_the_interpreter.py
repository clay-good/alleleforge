"""`aforge batch --workers 4` was 1.6x, because four threads queued for the interpreter.

A cohort's workers are threads, and 80% of a run is inside `scan_strand` — Rust that
touches no Python object. A PyO3 function holds the GIL unless it says otherwise, so four
workers were taking turns to run code that never needed the interpreter, and the cohort
scaled at 1.6x on four threads instead of near-linearly.

`Python::detach` releases it for the duration of the scan. `PyBackedStr` is what makes
that affordable: it keeps the Python `str` alive without copying, and the sequence here is
a whole contig — copying it per scan would trade the GIL for a memcpy of the genome.

Measured on a ten-variant cohort over a 2 Mb contig, in one process: 1.75x on two workers,
2.92x on four, 3.98x on eight, with byte-identical per-item summaries. This file does not
pin those numbers — a loaded machine moves them — it pins the property they come from.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from alleleforge.offtarget import _search

_LIB_RS = Path(__file__).resolve().parents[2] / "rust" / "src" / "lib.rs"

#: The kernels that run long enough for the GIL to matter, and must therefore release it.
#: Each takes a sequence and returns owned data, so there is nothing Python-side to touch
#: while it runs; the short ones (a single anchor, one k-mer lookup) are deliberately not
#: here, where the release would cost more than it saves.
_MUST_RELEASE = ("scan_strand", "evaluate_anchors", "fm_build", "fm_suffix_array")


def _function_body(name: str, source: str) -> str:
    start = source.index(f"fn {name}(")
    end = source.index("\n}\n", start)
    return source[start:end]


@pytest.mark.parametrize("kernel", _MUST_RELEASE)
def test_the_long_kernels_release_the_interpreter(kernel: str) -> None:
    """Read from the crate, so a rewrite that drops the release fails here."""
    source = _LIB_RS.read_text(encoding="utf-8")
    body = _function_body(kernel, source)
    assert "py.detach(" in body, (
        f"{kernel} runs for milliseconds to minutes without touching Python and holds "
        "the GIL for all of it; a threaded cohort serializes on it"
    )
    assert "PyBackedStr" in body or "text: PyBackedStr" in source, (
        f"{kernel} must borrow its sequence without copying: a contig copy per call "
        "trades the GIL for a memcpy of the genome"
    )


@pytest.mark.native
@pytest.mark.skipif(
    _search._NATIVE_SCAN_STRAND is None, reason="native aforge_native scan_strand not built"
)
def test_two_threads_scan_at_the_same_time() -> None:
    """The property itself: two scans on two threads take less than two scans' time.

    A wide margin (1.4x rather than the ~2x this machine shows), because the number is
    hardware- and load-dependent and this test is about the GIL, not the hardware. With
    the GIL held the ratio is 1.0 by construction.
    """
    import random

    rng = random.Random(5)
    contig = "".join(rng.choice("ACGT") for _ in range(400_000))
    spacer = "GACCATGCAACCTTGAACGT"
    scan = _search._NATIVE_SCAN_STRAND

    def once() -> None:
        scan(spacer, contig, "NGG", 4, 1, 1)

    once()  # warm any lazy work out of the measurement

    start = time.perf_counter()
    once()
    once()
    serial = time.perf_counter() - start

    threads = [threading.Thread(target=once) for _ in range(2)]
    start = time.perf_counter()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    parallel = time.perf_counter() - start

    assert serial / parallel > 1.4, (
        f"two scans on two threads took {parallel:.3f}s against {serial:.3f}s serially "
        f"({serial / parallel:.2f}x): the kernel is holding the interpreter"
    )
