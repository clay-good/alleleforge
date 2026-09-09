"""Cross-run cache for reference off-target reports (R4).

The reference candidate scan is the expensive, deterministic part of an
off-target search, and a cohort re-runs the *same* guide against the *same*
reference constantly. :class:`OffTargetCache` memoizes that result across runs,
content-addressed by the inputs that determine it.

**Safety first.** A wrong off-target report is a missed danger, so this cache is
deliberately conservative: :func:`alleleforge.offtarget.engine.search` uses it
**only** when the result is a pure function of the reference — i.e. with the
default CFD scorer and *no* population, haplotype, or patient augmentation (those
depend on external data the key cannot fully capture). When any of those is
present the search is computed fresh, never served from a possibly-stale entry.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from alleleforge.cache import ContentAddressedCache, hash_parts
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.guide import PAM
from alleleforge.types.offtarget import OffTargetReport
from alleleforge.types.sequence import GenomicInterval, canonical_contig


def reference_key(reference: ReferenceGenome) -> list[object]:
    """Return a stable identity for ``reference``: build, contig lengths, and the file.

    Build plus contig lengths is not an identity, it is a *shape*. `build` is a label
    the caller picks (`--reference-fasta any.fa --reference hg38`), and two FASTAs can
    share every contig name and length while differing in their bases — a soft-masked
    copy, a patched build, a locally edited genome. Measured, with two 4 kb references
    of one shape where the second contains a perfect match for the guide:

        second genome alone      2 sites, worst 1.000, specificity 0.333
        second genome, warm cache 0 sites, worst 0.000, specificity 1.000

    A cache hit turned a guide that cuts elsewhere into the most reassuring output the
    system can produce, on the opt-in flag whose whole promise is that it changes no
    result. An under-specified *label* fails to tell two records apart; an
    under-specified *key* serves one run the other's answer.

    Hashing the bases is genuinely out of reach (multi-gigabyte, per query), so the
    file's identity on this machine stands in for them: resolved path, size, and
    modification time. Two byte-identical copies at different paths no longer share
    entries — a miss, which costs a rescan — and a genome edited in place is correctly a
    different key rather than silently the same one.
    """
    contigs = sorted((c, reference.contig_length(c)) for c in reference.contigs)
    return [reference.build, contigs, _file_identity(reference.path)]


def _file_identity(path: Path) -> list[object]:
    """Return a cheap identity for the FASTA on this machine, or ``[]`` if unstattable.

    An empty identity is the conservative answer only because it is paired with the
    shape above: it degrades the key to what it used to be, so a reference whose file
    cannot be stat'd is no worse off than before, and every ordinary one is safer.
    """
    try:
        stat = Path(path).resolve().stat()
    except OSError:
        return []
    return [str(Path(path).resolve()), stat.st_size, stat.st_mtime_ns]


def search_signature(
    spacer: str,
    pam: PAM,
    *,
    reference: ReferenceGenome,
    mismatches: int,
    dna_bulges: int,
    rna_bulges: int,
    cfd_threshold: float,
    mit_threshold: float,
    regions: Sequence[GenomicInterval],
    on_target: GenomicInterval | None = None,
) -> str:
    """Return the content-addressed key for a reference-only default-scorer search.

    Excludes inputs that do not affect a reference-only result (``populations``,
    ``maf``, ``use_fm_index`` — the FM path is byte-identical to the linear scan).
    ``on_target`` — the locus the engine drops as the guide's own self-match — DOES
    change the result, so it is folded in here (naming-aware, matching
    ``engine._is_on_target``): otherwise a bare scan and an on-target-excluding scan
    collide on one key and one is served the other's report, silently either counting
    the self-match or hiding a perfect-score site.
    """
    region_parts = sorted((r.chrom, r.start, r.end, r.strand.value) for r in regions)
    on_target_part = (
        None
        if on_target is None
        else (
            canonical_contig(on_target.chrom),
            on_target.start,
            on_target.end,
            on_target.strand.value,
        )
    )
    return hash_parts(
        "offtarget-reference",
        spacer.upper(),
        pam.pattern,
        mismatches,
        dna_bulges,
        rna_bulges,
        cfd_threshold,
        mit_threshold,
        reference_key(reference),
        region_parts,
        on_target_part,
    )


class OffTargetCache:
    """A cross-run store of reference :class:`OffTargetReport`s, keyed by signature.

    Entries are **verified on read**. The key protects against serving the answer to a
    different question; nothing protected against serving a different answer to this one.
    Content-addressing says the inputs match — it says nothing about whether the bytes on
    disk are still the bytes that were written, and this store holds the safety finding
    itself. Measured on a two-site scan, editing the cached JSON's site list to `[]`:

        cold   2 sites, worst score 1.000
        warm   0 sites, worst score 0.000

    A perfect-match off-target became "clean", silently, on the opt-in flag whose whole
    promise is that it changes no result. The embedding cache in this same codebase has
    verified its bytes since it grew a checksum sidecar — the *input to a score*, while
    the finding was unguarded. A truncated file would have raised on parse; an edit that
    stays valid JSON, or a flipped bit inside a number, would not.

    A failed check raises :class:`~alleleforge.cache.CacheIntegrityError` rather than
    recomputing. Recomputing would give the right answer and hide that a store the run
    trusted has been altered, which is the more important thing to say — and `--cache` is
    opt-in, so declining it always leaves a working run.

    **What it costs.** A stored report is small — six real entries measured 521 bytes at
    the median, 880 at the largest — because it holds the nominated sites and not the
    genome they were found in. Re-hashing one is a few microseconds inside a warm hit of
    0.08 ms, against 3.7 ms for the scan it replaces on a 30 kb contig, and that ratio
    only grows with the reference: the hit is `O(entry)` and the scan is `O(genome)`.
    (Minimum of 25 runs on a loaded machine, so read the ratio and not the absolutes.)
    The check is free at the scale it protects, which is worth writing down beside the
    argument for having it — a defended property with no stated bill invites the next
    reader to guess at one.
    """

    #: Namespace version. Bump when the on-disk contract changes — v2 adds the checksum
    #: sidecar, which entries written under v1 do not have. A new namespace leaves the
    #: old entries unreferenced (inert) instead of failing every read closed on the
    #: missing sidecar, which is what a bare `verify=True` would have done to every cache
    #: already on a user's disk.
    NAMESPACE_VERSION = "v2"

    def __init__(self, *, root: str | Path | None = None) -> None:
        """Open the off-target report cache under ``root`` (default: the cache dir)."""
        self._store = ContentAddressedCache(
            f"offtarget/{self.NAMESPACE_VERSION}", root=root, verify=True
        )

    def get(self, signature: str) -> OffTargetReport | None:
        """Return the cached report for ``signature``, or ``None`` on a miss.

        Raises:
            CacheIntegrityError: If the entry's bytes do not match its checksum.
        """
        text = self._store.get_text(signature)
        return OffTargetReport.model_validate_json(text) if text is not None else None

    def put(self, signature: str, report: OffTargetReport) -> None:
        """Cache ``report`` under ``signature``."""
        self._store.put_text(signature, report.model_dump_json())

    def __len__(self) -> int:
        """Return the number of cached reports."""
        return len(self._store)
