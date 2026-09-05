#!/usr/bin/env python
"""Report native-vs-Python speedups for the off-target k-mer seeding (R2).

Reported, not gated: run ``python scripts/native_speedup.py`` to see wall-clock
for (a) the k-mer seed kernel native vs Python, (b) the seeded vs unseeded
off-target scan, (c) the haplotype-walk kernel, and (d) the FM-index vs linear
**anchor enumeration**, on a synthetic reference. Build the crate first for the
native numbers: ``cd rust && maturin develop --release``. Every pair below returns
identical hits (parity tests pin this); the kernels only change how the work is
found, never what is found.
"""

from __future__ import annotations

import random
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from alleleforge.genome.index import GenomeIndex
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget._haplotype import (
    apply_variants,
    native_haplotype_available,
    python_apply_variants,
)
from alleleforge.offtarget._kmer import (
    native_kmer_available,
    python_seed_positions,
    seed_positions,
)
from alleleforge.offtarget._search import scan_sequence
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM, Spacer
from alleleforge.types.sequence import DNASequence


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

    # Haplotype-walk materialization: apply a dense variant set to a window many
    # times (one per common haplotype per region, at cohort scale).
    print(f"\nnative haplotype kernel built: {native_haplotype_available()}")
    window = "".join(rng.choice("ACGT") for _ in range(2_000))
    edits = [(i, window[i], rng.choice("ACGT")) for i in range(0, 2_000, 7)]
    py_hap = _time(lambda: [python_apply_variants(window, 0, edits) for _ in range(2_000)])
    nat_hap = _time(lambda: [apply_variants(window, 0, edits) for _ in range(2_000)])
    print(f"haplotype materialization (2,000 windows × {len(edits)} edits)")
    print(f"  python : {py_hap * 1e3:8.2f} ms")
    print(
        f"  native : {nat_hap * 1e3:8.2f} ms  ({py_hap / nat_hap:.1f}x)"
        if native_haplotype_available()
        else "  native : (not built) — dispatch == python"
    )

    # FM-index vs linear ANCHOR ENUMERATION. Both paths then run the same
    # per-anchor alignment, so the index only replaces the O(n) PAM-matching pass,
    # paying a locate() per occurrence to do it. Which side wins is **workload
    # dependent** and the measurements here are not stable enough to generalize:
    # across runs the ratio has landed on both sides of 1.0 at the same contig
    # size, because the dominant cost is the number of in-budget hits the query
    # happens to have, not the contig length. Reported as a measurement to track
    # rather than a claim — do not quote a speedup from a single run of this.
    print("\nanchor enumeration: FM-index vs linear scan (identical hits)")
    for size in (300_000, 1_000_000):
        _fm_vs_linear(rng, spacer, pam, size)


def _fm_vs_linear(rng: random.Random, spacer: str, pam: PAM, size: int) -> None:
    """Time the FM-index anchor enumeration against the linear scan at ``size`` bp."""
    contig = "".join(rng.choice("ACGT") for _ in range(size))
    tmp = Path(tempfile.mkdtemp())
    fasta = tmp / "bench.fa"
    fasta.write_text(f">chr1\n{contig}\n")
    reference = ReferenceGenome(fasta, build="hg38")
    index = GenomeIndex.build_genome(reference, cache_dir=tmp / "idx")
    probe = Spacer(sequence=DNASequence(spacer))
    try:
        linear = _time(
            lambda: search(probe, pam, reference=reference, use_fm_index=False), repeat=1
        )
        fm = _time(lambda: search(probe, pam, reference=reference, genome_index=index), repeat=1)
    finally:
        index.close()
    verdict = "faster" if fm < linear else "SLOWER"
    print(
        f"  {size:>9,} bp   linear {linear:6.2f}s   "
        f"fm-index {fm:6.2f}s   ({linear / fm:.2f}x, {verdict})"
    )


if __name__ == "__main__":
    main()
