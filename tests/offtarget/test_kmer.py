"""The k-mer seed prefilter is a proven superset: seeded scan == brute force.

The off-target scan is safety-critical — a dropped hit is a missed danger — so the
seed-and-extend prefilter is held to an exhaustive equivalence test: across
hundreds of randomized references, spacers, PAMs, and mismatch/bulge budgets, the
seeded scan (default) must return *exactly* the unseeded brute-force scan. The
native k-mer kernel is additionally pinned byte-for-byte to the Python seeding.
"""

from __future__ import annotations

import random

import pytest

from alleleforge import _native
from alleleforge.offtarget._kmer import (
    covered_prefix,
    native_kmer_available,
    python_seed_positions,
    seed_length,
    seed_positions,
)
from alleleforge.offtarget._search import scan_sequence
from alleleforge.types.guide import PAM


def test_seed_length_bound() -> None:
    assert seed_length(20, 4) == 4  # 20 // 5
    assert seed_length(20, 6) == 2  # 20 // 7
    assert seed_length(5, 6) == 0  # budget exceeds length -> seeding disabled


def test_python_seed_positions_basic() -> None:
    # spacer 2-mers: AC, CG, GT; find them in the reference.
    assert python_seed_positions("TTACGTTT", "ACGT", 2) == [2, 3, 4]
    assert python_seed_positions("TTTTTT", "ACGT", 2) == []
    assert python_seed_positions("ACGT", "ACGT", 0) == []


def test_covered_prefix_range_any() -> None:
    # seeds at positions 2 and 5 with k=2 cover indices {2,3,5,6}.
    c = covered_prefix(8, [2, 5], 2)
    assert c[4] - c[2] == 2  # [2,4) fully covered
    assert c[5] - c[4] == 0  # index 4 not covered
    assert c[7] - c[5] == 2  # [5,7) covered


_PAMS = [PAM(pattern="NGG"), PAM(pattern="NRG")]


def _random_seq(rng: random.Random, n: int, *, with_n: bool = False) -> str:
    alphabet = "ACGTN" if with_n else "ACGT"
    return "".join(rng.choice(alphabet) for _ in range(n))


def test_seeded_scan_equals_brute_force_exhaustive() -> None:
    rng = random.Random(20240501)
    cases = 0
    for _ in range(400):
        n = rng.randint(16, 22)
        spacer = _random_seq(rng, n)
        seq = _random_seq(rng, rng.randint(40, 130), with_n=rng.random() < 0.3)
        pam = rng.choice(_PAMS)
        mismatches = rng.randint(0, 4)
        dna_bulges = rng.randint(0, 1)
        rna_bulges = rng.randint(0, 1)
        common = dict(mismatches=mismatches, dna_bulges=dna_bulges, rna_bulges=rna_bulges)
        seeded = scan_sequence("chr1", seq, spacer, pam, seed=True, **common)  # type: ignore[arg-type]
        brute = scan_sequence("chr1", seq, spacer, pam, seed=False, **common)  # type: ignore[arg-type]
        assert seeded == brute
        cases += 1
    assert cases == 400


def test_seeding_disabled_for_tiny_spacer_matches_brute() -> None:
    # n=6 with E=6 -> seed_length 0 -> seeding disabled; results still match.
    seq = "ACGTACGTACGTACGTACGTAGG"
    seeded = scan_sequence(
        "chr1", seq, "ACGTAC", PAM(pattern="NGG"), mismatches=4, dna_bulges=1, rna_bulges=1
    )
    brute = scan_sequence(
        "chr1",
        seq,
        "ACGTAC",
        PAM(pattern="NGG"),
        mismatches=4,
        dna_bulges=1,
        rna_bulges=1,
        seed=False,
    )
    assert seeded == brute


# --- native k-mer kernel parity (skips unless the crate is built) ----------------

requires_native = pytest.mark.skipif(
    not native_kmer_available(), reason="native aforge_native k-mer kernel not built"
)


def test_native_kmer_available_reflects_built_kernel() -> None:
    ext = getattr(_native, "_ext", None)
    expected = _native.NATIVE_AVAILABLE and ext is not None and hasattr(ext, "kmer_seed_positions")
    assert native_kmer_available() is expected


@requires_native
@pytest.mark.native
def test_native_seed_positions_match_python() -> None:
    rng = random.Random(7)
    ext = _native._ext  # type: ignore[attr-defined]
    for _ in range(200):
        spacer = _random_seq(rng, rng.randint(8, 22))
        seq = _random_seq(rng, rng.randint(20, 120), with_n=rng.random() < 0.3)
        k = rng.randint(1, 6)
        assert list(ext.kmer_seed_positions(seq, spacer, k)) == python_seed_positions(
            seq, spacer, k
        )


@requires_native
@pytest.mark.native
def test_native_seeded_scan_equals_brute_force() -> None:
    rng = random.Random(11)
    for _ in range(150):
        n = rng.randint(16, 22)
        spacer = _random_seq(rng, n)
        seq = _random_seq(rng, rng.randint(40, 130), with_n=rng.random() < 0.3)
        pam = rng.choice(_PAMS)
        common = dict(
            mismatches=rng.randint(0, 4),
            dna_bulges=rng.randint(0, 1),
            rna_bulges=rng.randint(0, 1),
        )
        # seed=True uses the native kernel (crate built); compare to brute force.
        seeded = scan_sequence("chr1", seq, spacer, pam, seed=True, **common)  # type: ignore[arg-type]
        brute = scan_sequence("chr1", seq, spacer, pam, seed=False, **common)  # type: ignore[arg-type]
        assert seeded == brute


def test_seed_positions_dispatch_matches_python() -> None:
    # The public dispatcher agrees with the pure-Python path (native or not).
    rng = random.Random(3)
    for _ in range(50):
        spacer = _random_seq(rng, rng.randint(8, 20))
        seq = _random_seq(rng, rng.randint(20, 80))
        k = rng.randint(1, 5)
        assert seed_positions(seq, spacer, k) == python_seed_positions(seq, spacer, k)
