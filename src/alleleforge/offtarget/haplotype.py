"""Haplotype-aware off-target evaluation over common phased haplotypes.

A population variant in isolation is one thing; a *combination* of variants
co-inherited on a common haplotype is another, and can create an off-target that
no single variant does. This module walks the common haplotypes spanning the
search region (from the Phase 3 1000G/HGDP panels), applies each haplotype's full
variant set to the reference, and reports PAM-anchored hits the haplotype creates
or strengthens.

The genome-scale walk is the Rust ``haplotype.rs`` kernel; this is the correct
pure-Python orchestration used until that crate is built and in CI.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from alleleforge.data.haplotypes import Haplotype
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget._search import Hit, SearchBudget, SiteProvenance, scan_sequence
from alleleforge.types.guide import PAM
from alleleforge.types.offtarget import SiteOrigin
from alleleforge.types.sequence import CoordinateSystem, DNASequence, GenomicInterval, Strand
from alleleforge.types.variant import Variant


def _apply_all(seq: str, window_start: int, variants: Sequence[Variant]) -> str | None:
    """Apply every variant (right-to-left) to ``seq``; ``None`` on a ref clash."""
    out = seq
    for var in sorted(variants, key=lambda v: v.pos, reverse=True):
        rel = var.pos - window_start
        if rel < 0 or rel + len(var.ref) > len(out):
            return None
        if out[rel : rel + len(var.ref)].upper() != var.ref.upper():
            return None
        out = out[:rel] + var.alt + out[rel + len(var.ref) :]
    return out


def enumerate_haplotype_sites(
    spacer: str | DNASequence,
    pam: PAM,
    *,
    reference: ReferenceGenome,
    haplotypes: Iterable[Haplotype],
    populations: Sequence[str] | None = None,
    min_freq: float = 0.001,
    mismatches: int = 4,
    dna_bulges: int = 1,
    rna_bulges: int = 1,
) -> list[tuple[Hit, SiteProvenance]]:
    """Enumerate off-target hits created or strengthened by common haplotypes.

    Args:
        spacer: The on-target guide spacer, 5'->3'.
        pam: The PAM pattern to anchor on (broadened for low-stringency PAMs).
        reference: The reference genome.
        haplotypes: Common haplotypes spanning the region (from a panel).
        populations: Ancestry labels to consider; ``None`` uses each haplotype's.
        min_freq: Minimum per-population haplotype frequency to include.
        mismatches: Maximum base mismatches.
        dna_bulges: Maximum DNA bulges.
        rna_bulges: Maximum RNA bulges.

    Returns:
        ``(hit, provenance)`` pairs with ``provenance.origin = POPULATION``.
    """
    sp = str(spacer).upper()
    pam_len = len(pam.pattern)
    margin = len(sp) + pam_len + 1
    kw: SearchBudget = {
        "mismatches": mismatches,
        "dna_bulges": dna_bulges,
        "rna_bulges": rna_bulges,
    }
    out: list[tuple[Hit, SiteProvenance]] = []
    for hap in haplotypes:
        if hap.is_reference or hap.max_freq(populations) < min_freq:
            continue
        chrom = hap.interval.chrom
        if chrom not in reference.contigs:
            continue
        start = max(0, hap.interval.start - margin)
        end = hap.interval.end + margin
        ref_seq = str(
            reference.fetch(
                GenomicInterval(
                    chrom=chrom,
                    start=start,
                    end=end,
                    strand=Strand.PLUS,
                    coordinate_system=CoordinateSystem.ZERO_BASED_HALF_OPEN,
                )
            )
        )
        alt_seq = _apply_all(ref_seq, start, hap.variants)
        if alt_seq is None:
            continue
        ref_edits: dict[tuple[Strand, int, int], int] = {}
        for h in scan_sequence(chrom, ref_seq, sp, pam, offset=start, **kw):
            key = (h.strand, h.start, h.end)
            ref_edits[key] = min(ref_edits.get(key, h.edits), h.edits)
        var_positions = [v.pos for v in hap.variants]
        pops = (
            tuple(p for p in populations if hap.frequencies.get(p, 0.0) >= min_freq)
            if populations is not None
            else hap.populations
        )
        prov = SiteProvenance(
            origin=SiteOrigin.POPULATION,
            causal_allele=";".join(f"{v.chrom}:{v.pos}:{v.ref}>{v.alt}" for v in hap.variants),
            populations=pops,
            frequency=hap.max_freq(populations),
            ancestries=dict(hap.frequencies),
        )
        for h in scan_sequence(chrom, alt_seq, sp, pam, offset=start, **kw):
            if not any(h.start - pam_len <= p < h.end + pam_len for p in var_positions):
                continue
            prior = ref_edits.get((h.strand, h.start, h.end))
            if prior is None or h.edits < prior:
                out.append((h, prov))
    return out
