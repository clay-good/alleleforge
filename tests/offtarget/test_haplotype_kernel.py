"""The haplotype-walk kernel: native materialization == pure-Python fallback.

Materializing a haplotype's alternative sequence feeds the safety-critical
off-target scan, so the native ``haplotype.rs`` kernel is held to byte-identical
equivalence with the proven pure-Python ``python_apply_variants``: across
thousands of randomized windows, variant sets, indels, ``N`` bases, lowercase
reference assertions, and out-of-window / clashing positions, both paths must
agree exactly. The native parity test is marked ``native`` and skips unless the
crate is built (CI builds it in the dedicated rust job).
"""

from __future__ import annotations

import random

import pytest

from alleleforge import _native
from alleleforge.offtarget._haplotype import (
    apply_variants,
    native_haplotype_available,
    python_apply_variants,
)


def test_python_apply_variants_substitution() -> None:
    assert python_apply_variants("ACGT", 0, [(1, "C", "T")]) == "ATGT"


def test_python_apply_variants_reference_clash_returns_none() -> None:
    assert python_apply_variants("ACGT", 0, [(1, "A", "T")]) is None


def test_python_apply_variants_out_of_window_returns_none() -> None:
    assert python_apply_variants("ACGT", 0, [(10, "C", "T")]) is None
    assert python_apply_variants("ACGT", 5, [(4, "C", "T")]) is None  # rel < 0


def test_python_apply_variants_indels_right_to_left() -> None:
    # An insertion to the right and a substitution to the left compose cleanly
    # because edits are applied in descending-position order.
    assert python_apply_variants("ACGT", 0, [(0, "A", "TT"), (2, "G", "GGG")]) == "TTCGGGT"


def test_python_apply_variants_case_insensitive_ref() -> None:
    # The reference assertion is case-insensitive; the alt is spliced verbatim.
    assert python_apply_variants("acgt", 0, [(1, "C", "x")]) == "axgt"


def test_window_start_offset() -> None:
    assert python_apply_variants("ACGT", 100, [(101, "C", "T")]) == "ATGT"


def _random_case(rng: random.Random) -> tuple[str, int, list[tuple[int, str, str]]]:
    n = rng.randint(5, 40)
    seq = "".join(rng.choice("ACGTN") for _ in range(n))
    window_start = rng.randint(0, 5)
    edits: list[tuple[int, str, str]] = []
    for _ in range(rng.randint(0, 4)):
        pos = window_start + rng.randint(-2, n + 2)
        ref = "".join(rng.choice("acgtACGT") for _ in range(rng.randint(1, 3)))
        alt = "".join(rng.choice("ACGT") for _ in range(rng.randint(0, 3)))
        edits.append((pos, ref, alt))
    return seq, window_start, edits


def test_dispatch_matches_python() -> None:
    """The public dispatcher agrees with the pure-Python path (native or not)."""
    rng = random.Random(2024)
    for _ in range(500):
        seq, ws, edits = _random_case(rng)
        assert apply_variants(seq, ws, edits) == python_apply_variants(seq, ws, edits)


requires_native = pytest.mark.skipif(
    not native_haplotype_available(), reason="native aforge_native haplotype kernel not built"
)


def test_native_haplotype_available_reflects_built_kernel() -> None:
    ext = getattr(_native, "_ext", None)
    expected = (
        _native.NATIVE_AVAILABLE and ext is not None and hasattr(ext, "haplotype_apply_variants")
    )
    assert native_haplotype_available() is expected


@requires_native
@pytest.mark.native
def test_native_apply_variants_matches_python() -> None:
    rng = random.Random(99)
    ext = _native._ext  # type: ignore[attr-defined]
    for _ in range(3000):
        seq, ws, edits = _random_case(rng)
        assert ext.haplotype_apply_variants(seq, ws, edits) == python_apply_variants(seq, ws, edits)
