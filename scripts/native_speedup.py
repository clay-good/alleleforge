#!/usr/bin/env python
"""Report native-vs-Python speedups for the off-target hot path.

Reported, not gated: run ``python scripts/native_speedup.py`` to see wall-clock
for (a) the k-mer seed kernel native vs Python, (b) the seeded vs unseeded
off-target scan, (c) the haplotype-walk kernel, (d) the FM-index vs linear
**anchor enumeration**, (e) the bulged-alignment kernel, (f) the per-anchor
evaluation kernel, and (g) the contig fold to the index alphabet, on a synthetic
reference. Build the crate first for the native numbers:
``cd rust && maturin develop --release``. Every pair below returns identical
results (parity tests pin this); the kernels only change how the work is found,
never what is found.

Why this script exists in this shape: the round log carries a dozen performance
claims ("2.62s -> 1.16s", "+94.5%", "28%") and for a while covered four of the
optimizations while the crate had grown to six. A number that lives only in prose
cannot be re-measured by anyone, which is the same standard `scripts/reproduce.py`
holds the *scientific* result to. `test_the_speedup_script_covers_every_kernel`
fails when the crate gains a function this does not time.
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


#: Native kernel -> the heading of the section that times it. Keyed by the name the
#: crate registers in ``rust/src/lib.rs``; the script calls each one through its
#: Python wrapper, so this map is what makes the coverage checkable.
#: ``test_the_speedup_script_times_every_kernel`` fails if the crate gains a
#: function that is missing here, or if a name here is no longer registered.
TIMED_KERNELS = {
    "kmer_seed_positions": "k-mer seed lookup",
    "haplotype_apply_variants": "haplotype materialization",
    "fm_build": "anchor enumeration: FM-index vs linear scan",
    "fm_count": "anchor enumeration: FM-index vs linear scan",
    "fm_locate": "anchor enumeration: FM-index vs linear scan",
    "fm_suffix_array": "anchor enumeration: FM-index vs linear scan",
    "align_best_with_removed_base": "bulged alignment",
    "evaluate_anchor": "per-anchor evaluation",
}


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

    _alignment_and_evaluation(rng)
    _contig_fold(rng)


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


def _alignment_and_evaluation(rng: random.Random) -> None:
    """Time the two innermost kernels against their Python fallbacks.

    These run per PAM-positive anchor — half a million times over 2 Mb — so they are
    timed over a batch of realistic shapes rather than once. `evaluate_anchor`
    subsumes the ungapped comparison and both bulge directions, so a scan crosses the
    FFI boundary once per anchor instead of three times.
    """
    from alleleforge.offtarget._search import (
        _NATIVE_EVALUATE,
        _NATIVE_REMOVED_BASE,
        _python_best_with_removed_base,
        _python_evaluate,
    )

    spacer = "".join(rng.choice("ACGT") for _ in range(20))
    windows = ["".join(rng.choice("ACGT") for _ in range(21)) for _ in range(20_000)]
    seqs = ["".join(rng.choice("ACGT") for _ in range(60)) for _ in range(20_000)]

    print("\nbulged alignment (per anchor, 20,000 shapes)")
    py = _time(lambda: [_python_best_with_removed_base(w, spacer, 4) for w in windows])
    print(f"  python : {py * 1e3:8.2f} ms")
    if _NATIVE_REMOVED_BASE is not None:
        nat = _time(lambda: [_NATIVE_REMOVED_BASE(w, spacer, 4) for w in windows])
        print(f"  native : {nat * 1e3:8.2f} ms  ({py / nat:.1f}x)")
    else:
        print("  native : (not built) - dispatch == python")

    print("\nper-anchor evaluation (20,000 anchors)")
    kw = {"max_mm": 4, "dna_bulges": 1, "rna_bulges": 1}
    py = _time(lambda: [_python_evaluate(spacer, s, 40, 3, **kw) for s in seqs])
    print(f"  python : {py * 1e3:8.2f} ms")
    if _NATIVE_EVALUATE is not None:
        nat = _time(lambda: [_NATIVE_EVALUATE(spacer, s, 40, 4, 1, 1) for s in seqs])
        print(f"  native : {nat * 1e3:8.2f} ms  ({py / nat:.1f}x)")
    else:
        print("  native : (not built) - dispatch == python")


def _contig_fold(rng: random.Random) -> None:
    """Time the fold to the index alphabet: `str.translate` vs the per-base loop.

    Not a native kernel — a pure-Python change — but it is on the same hot path,
    runs once per sequence per `search()` (uncached, so once per candidate), and its
    claim belongs with the others rather than only in the log.
    """
    from alleleforge.offtarget._search import _INDEX_ALPHABET, _sanitize

    def previous(seq: str) -> str:
        if all(b in _INDEX_ALPHABET for b in seq):
            return seq
        return "".join(b if b in _INDEX_ALPHABET else "N" for b in seq)

    print("\ncontig fold to the index alphabet (once per sequence per search)")
    for label, contig in (
        ("clean 2 Mb", "".join(rng.choice("ACGTN") for _ in range(2_000_000))),
        ("one stray base", "".join(rng.choice("ACGTN") for _ in range(1_999_999)) + "R"),
    ):
        before = _time(lambda c=contig: previous(c))
        after = _time(lambda c=contig: _sanitize(c))
        assert previous(contig) == _sanitize(contig), "the fold changed its answer"
        print(
            f"  {label:16} per-base loop {before * 1e3:7.1f} ms   "
            f"str.translate {after * 1e3:6.1f} ms   ({before / after:.1f}x)"
        )


if __name__ == "__main__":
    main()
