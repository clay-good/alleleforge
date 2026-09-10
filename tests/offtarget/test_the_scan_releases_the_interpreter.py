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

from pathlib import Path

import pytest

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


# A behavioural companion to the check above was written and then removed, which is worth
# recording. The intent was to run a scan on one thread and count how much Python ran on
# another; the trouble is demonstrating that it *fails*. A kernel that holds the GIL is
# not something this crate can express by deleting one call — `py.detach` is what gives
# the closure access to the borrowed strings, so the version without it does not compile —
# and every timing-shaped instrument tried here was drowned by a loaded machine: two
# genuinely overlapping scans measured 1.25x, and a tick-rate calibration moved by 7x
# between two consecutive moments in the same process.
#
# So this file asserts the property at the source, where it is exact, and the *value* of
# the release is measured where it can be: `tests/design/test_parallelism_is_parallel.py`
# requires the cohort pool to overlap, and the round log carries the cohort speedups
# (1.75x / 2.92x / 3.98x on two, four and eight workers) with their method.
#
# A check that cannot be shown to fail is not a check, and shipping one would have been
# the exact defect this suite keeps finding in other people's work.
