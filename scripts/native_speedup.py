#!/usr/bin/env python
"""Report native-vs-Python speedups for the off-target k-mer seeding (R2).

Reported, not gated: run ``python scripts/native_speedup.py`` to see wall-clock
for (a) the k-mer seed kernel native vs Python and (b) the seeded vs unseeded
off-target scan, on a synthetic reference. Build the crate first for the native
numbers: ``cd rust && maturin develop --release``. The seeded and unseeded scans
return identical hits (a parity test pins this); seeding only prunes work.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable

from alleleforge.offtarget._kmer import (
    native_kmer_available,
    python_seed_positions,
    seed_positions,
)
from alleleforge.offtarget._search import scan_sequence
from alleleforge.types.guide import PAM


def _time(fn: Callable[[], object], *, repeat: int = 3) -> float:
    """Return the best wall-clock seconds over ``repeat`` runs of ``fn``."""
    best = float("inf")
    for _ in range(repeat):
        start = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - start)
    return best


def main() -> None:
    """Print the seeding and scan benchmarks for a synthetic reference."""
    rng = random.Random(20240501)
    reference = "".join(rng.choice("ACGT") for _ in range(200_000))
    spacer = "".join(rng.choice("ACGT") for _ in range(20))
    pam = PAM(pattern="NGG")
    k = 4

    print(f"native k-mer kernel built: {native_kmer_available()}")
    print(f"reference: {len(reference):,} bp · spacer: {len(spacer)} nt\n")

    py = _time(lambda: python_seed_positions(reference, spacer, k))
    nat = _time(lambda: seed_positions(reference, spacer, k, prefer_native=True))
    print("k-mer seed lookup")
    print(f"  python : {py * 1e3:8.2f} ms")
    print(
        f"  native : {nat * 1e3:8.2f} ms  ({py / nat:.1f}x)"
        if native_kmer_available()
        else "  native : (not built) — dispatch == python"
    )

    # Seeding auto-engages only when the seed is selective (k >= 5, i.e. low edit
    # budget / high stringency); at the default budget (k=2) it is a no-op and the
    # scan is unchanged. Report both regimes.
    print("\noff-target scan (both strands)")
    for label, mm in (("high-stringency (mismatches=1)", 1), ("default (mismatches=4)", 4)):
        kw = dict(mismatches=mm, dna_bulges=0, rna_bulges=0)
        brute = _time(
            lambda mm=mm, kw=kw: scan_sequence("c", reference, spacer, pam, seed=False, **kw),
            repeat=1,
        )  # noqa: E501
        seeded = _time(
            lambda mm=mm, kw=kw: scan_sequence("c", reference, spacer, pam, seed=True, **kw),
            repeat=1,
        )  # noqa: E501
        print(f"  {label}")
        print(f"    brute force : {brute * 1e3:8.2f} ms")
        print(f"    seeded      : {seeded * 1e3:8.2f} ms  ({brute / seeded:.1f}x)")


if __name__ == "__main__":
    main()
