"""k-mer seed-and-extend prefilter for off-target candidate enumeration.

The brute-force off-target scan evaluates a spacer alignment at *every* PAM
anchor. This module narrows that to the anchors that could possibly be a hit, by
the standard **seed-and-extend** argument:

For an alignment within a total edit budget ``E = mismatches + dna_bulges +
rna_bulges``, partition the spacer into ``E + 1`` contiguous blocks of length
``k = ⌊n / (E + 1)⌋``. At most ``mismatches`` blocks carry a substitution and at
most ``dna_bulges + rna_bulges`` blocks are cut by an indel, so at least one
block is **uncut and substitution-free** — it matches the genomic target exactly
and contiguously. Therefore every in-budget hit shares at least one exact length
-``k`` substring (a *seed*) with the spacer, located inside its protospacer
window. Evaluating only anchors whose window contains a seed is a **superset** of
the brute-force candidate set: it can never drop a hit, only skip windows that
provably contain none.

The seed lookup itself has a native Rust kernel (``kmer.rs``); this module is the
pure-Python equivalent and the dispatcher, mirroring how the FM-index degrades.
``seed_positions`` is what both paths agree on (a parity test pins it).
"""

from __future__ import annotations

from alleleforge import _native


def native_kmer_available() -> bool:
    """Return ``True`` if the native crate exposes the k-mer seed kernel."""
    ext = getattr(_native, "_ext", None)
    return _native.NATIVE_AVAILABLE and ext is not None and hasattr(ext, "kmer_seed_positions")


def python_seed_positions(sequence: str, spacer: str, k: int) -> list[int]:
    """Return sorted start positions ``p`` where ``sequence[p:p+k]`` is a spacer k-mer.

    A *spacer k-mer* is any length-``k`` substring of ``spacer``. The result is
    the set of reference offsets at which the spacer shares an exact ``k``-mer
    with ``sequence`` (the seed anchors). Returns ``[]`` for ``k < 1`` or inputs
    shorter than ``k``.
    """
    if k < 1 or len(spacer) < k or len(sequence) < k:
        return []
    spacer_kmers = {spacer[i : i + k] for i in range(len(spacer) - k + 1)}
    return [p for p in range(len(sequence) - k + 1) if sequence[p : p + k] in spacer_kmers]


def seed_positions(sequence: str, spacer: str, k: int, *, prefer_native: bool = True) -> list[int]:
    """Return the seed anchor positions, via the native kernel when available.

    Args:
        sequence: The (single-strand) reference sequence to seed against.
        spacer: The guide spacer whose k-mers are the seeds.
        k: Seed length.
        prefer_native: Use the Rust kernel when it is built.

    Returns:
        Sorted reference start positions sharing an exact ``k``-mer with ``spacer``.
    """
    if prefer_native and native_kmer_available():  # pragma: no cover - native not built in CI
        ext = _native._ext  # type: ignore[attr-defined]  # optional native kernel
        positions: list[int] = list(ext.kmer_seed_positions(sequence, spacer, k))
        return positions
    return python_seed_positions(sequence, spacer, k)


def seed_length(spacer_length: int, edit_budget: int) -> int:
    """Return the seed length ``k = ⌊n / (E + 1)⌋`` for the seed-and-extend bound.

    Returns ``0`` when the edit budget is so large relative to the spacer that no
    block survives (``E + 1 > n``); callers must then fall back to a full scan,
    because seeding would no longer be a correctness-preserving superset.
    """
    return spacer_length // (edit_budget + 1)


def covered_prefix(length: int, positions: list[int], k: int) -> list[int]:
    """Return a half-open prefix sum over indices covered by any seed ``[p, p+k)``.

    The returned array ``c`` has length ``length + 1`` with ``c[0] == 0``;
    ``c[hi] - c[lo]`` counts the covered indices in ``[lo, hi)``, giving an O(1)
    "does this window contain a seed?" test during the scan.
    """
    diff = [0] * (length + 1)
    for p in positions:
        if p < length:
            diff[p] += 1
            diff[min(length, p + k)] -= 1
    prefix = [0] * (length + 1)
    running = 0
    for i in range(length):
        running += diff[i]
        prefix[i + 1] = prefix[i] + (1 if running > 0 else 0)
    return prefix
