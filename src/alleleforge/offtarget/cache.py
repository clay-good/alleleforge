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
from alleleforge.types.sequence import GenomicInterval


def reference_key(reference: ReferenceGenome) -> list[object]:
    """Return a stable identity for ``reference`` (build + contig lengths).

    Standard assemblies are uniquely determined by their build name and the set of
    contig lengths; this avoids hashing multi-gigabyte FASTA content on every
    query. Two references that share a build *and* every contig length are treated
    as identical sequence — true for the pinned builds AlleleForge ships.
    """
    contigs = sorted((c, reference.contig_length(c)) for c in reference.contigs)
    return [reference.build, contigs]


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
) -> str:
    """Return the content-addressed key for a reference-only default-scorer search.

    Excludes inputs that do not affect a reference-only result (``populations``,
    ``maf``, ``use_fm_index`` — the FM path is byte-identical to the linear scan).
    """
    region_parts = sorted((r.chrom, r.start, r.end, r.strand.value) for r in regions)
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
    )


class OffTargetCache:
    """A cross-run store of reference :class:`OffTargetReport`s, keyed by signature."""

    def __init__(self, *, root: str | Path | None = None) -> None:
        """Open the off-target report cache under ``root`` (default: the cache dir)."""
        self._store = ContentAddressedCache("offtarget", root=root)

    def get(self, signature: str) -> OffTargetReport | None:
        """Return the cached report for ``signature``, or ``None`` on a miss."""
        text = self._store.get_text(signature)
        return OffTargetReport.model_validate_json(text) if text is not None else None

    def put(self, signature: str, report: OffTargetReport) -> None:
        """Cache ``report`` under ``signature``."""
        self._store.put_text(signature, report.model_dump_json())

    def __len__(self) -> int:
        """Return the number of cached reports."""
        return len(self._store)
