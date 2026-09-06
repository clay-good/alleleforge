"""Native bulged-alignment parity: the Rust kernel matches the Python fallback.

`_best_with_removed_base` is the innermost function of the off-target scan -- two calls
per PAM-positive anchor, one per bulge direction, a million of them over 2 Mb, and 57% of
the scan's self time once the cheaper wins were taken. It now dispatches to a Rust kernel
when the crate is built.

The project's contract for every native kernel is that an unbuilt crate changes the
*speed* of a run and not its results, so this asserts the two paths are byte-identical
rather than merely both plausible. A wrong mismatch count here becomes a wrong number on a
reported off-target site, which is the one place this project cannot afford to be
approximately right.

Marked `native` and skipped when the crate is not built, matching the FM-index parity
suite. The randomized differential of the *Python* path against the naive definition
lives in `test_alignment_equivalence.py`; chaining the two pins the native kernel to the
definition, not merely to the other implementation.
"""

from __future__ import annotations

import random

import pytest

from alleleforge.offtarget._search import (
    _best_with_removed_base,
    _python_best_with_removed_base,
    native_align_available,
)

requires_native = pytest.mark.skipif(
    not native_align_available(), reason="native aforge_native align kernel not built"
)


@requires_native
@pytest.mark.native
def test_the_dispatcher_is_actually_using_the_native_kernel() -> None:
    """A floor: without this the parity tests below could be Python against Python."""
    from alleleforge.offtarget._search import _NATIVE_REMOVED_BASE

    assert _NATIVE_REMOVED_BASE is not None
    assert _best_with_removed_base is not _python_best_with_removed_base


@requires_native
@pytest.mark.native
def test_native_matches_python_over_randomized_inputs() -> None:
    rng = random.Random(20260906)
    for _ in range(30_000):
        n = rng.randint(1, 24)
        shorter = "".join(rng.choice("ACGTN") for _ in range(n))
        if rng.random() < 0.4:
            # A real single-base bulge, so the in-budget branch is exercised too.
            r = rng.randrange(n + 1)
            longer = shorter[:r] + rng.choice("ACGTN") + shorter[r:]
        else:
            longer = "".join(rng.choice("ACGTN") for _ in range(n + 1))
        max_mm = rng.randint(0, 8)

        assert _best_with_removed_base(longer, shorter, max_mm) == _python_best_with_removed_base(
            longer, shorter, max_mm
        ), (longer, shorter, max_mm)


@requires_native
@pytest.mark.native
@pytest.mark.parametrize(
    ("longer", "shorter", "max_mm"),
    [
        ("A", "", 0),  # the degenerate empty target
        ("AC", "A", 0),
        ("ACGTA", "ACGT", 0),  # a clean removal
        ("TTTTT", "ACGT", 0),  # nothing within budget
        ("TTTTT", "ACGT", 4),  # everything within a generous budget
        ("ACGT", "ACGT", 4),  # equal lengths: not a single-base bulge
        ("AC", "ACGT", 4),  # shorter is longer: not a bulge either
        ("NNNNN", "NNNN", 0),  # ambiguity codes compare as plain bytes
    ],
)
def test_native_matches_python_on_the_edges(longer: str, shorter: str, max_mm: int) -> None:
    """The cases a random generator reaches rarely or never."""
    assert _best_with_removed_base(longer, shorter, max_mm) == _python_best_with_removed_base(
        longer, shorter, max_mm
    )


@requires_native
@pytest.mark.native
def test_a_length_that_is_not_a_single_base_bulge_is_refused_by_both() -> None:
    """Neither path may invent an alignment it cannot score."""
    for longer, shorter in (("ACGTAC", "ACGT"), ("ACG", "ACGT"), ("", "ACGT")):
        assert _best_with_removed_base(longer, shorter, 4) is None
        assert _python_best_with_removed_base(longer, shorter, 4) is None
