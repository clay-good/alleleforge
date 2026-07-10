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
from alleleforge.offtarget._haplotype import apply_variants
from alleleforge.offtarget._search import (
    Hit,
    SearchBudget,
    SiteProvenance,
    _reindex_alt_hits,
    scan_sequence,
)
from alleleforge.offtarget.population import _reference_best, _strengthens, _touches
from alleleforge.offtarget.scoring import CfdScorer, OffTargetScorer
from alleleforge.types.guide import PAM
from alleleforge.types.offtarget import SiteOrigin
from alleleforge.types.sequence import (
    CoordinateSystem,
    DNASequence,
    GenomicInterval,
    Strand,
    canonical_contig,
)
from alleleforge.types.variant import Variant


def _clashes(ref_seq: str, window_start: int, var: Variant) -> bool:
    """Return ``True`` if ``var``'s asserted reference does not match the window."""
    rel = var.pos - window_start
    if rel < 0 or rel + len(var.ref) > len(ref_seq):
        return True
    return ref_seq[rel : rel + len(var.ref)].upper() != var.ref.upper()


def _partition_variants(
    ref_seq: str, window_start: int, variants: Sequence[Variant]
) -> tuple[list[Variant], list[Variant]]:
    """Split a haplotype's variants into (applied, skipped) against the window.

    A variant is skipped when its asserted reference base clashes with the build;
    the rest are still applied, so one bad variant no longer discards the whole
    haplotype's nominations. Variants are non-overlapping on a phased haplotype, so
    each clash decision is independent of the others.
    """
    applied: list[Variant] = []
    skipped: list[Variant] = []
    for var in variants:
        (skipped if _clashes(ref_seq, window_start, var) else applied).append(var)
    return applied, skipped


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
    scorer: OffTargetScorer | None = None,
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
        scorer: The specificity scorer used to judge whether a haplotype hit
            strengthens a reference hit at the same placement (default
            :class:`CfdScorer`); pass the engine's primary scorer so nomination and
            reporting agree.

    Returns:
        ``(hit, provenance)`` pairs with ``provenance.origin = POPULATION``.
    """
    sp = str(spacer).upper()
    scorer = scorer if scorer is not None else CfdScorer()
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
        # Reconcile the panel's contig name against the reference's naming style
        # ("1" vs "chr1"): a raw membership check would silently skip every
        # haplotype on a naming mismatch, yielding zero haplotype-aware off-targets
        # even though `reference.fetch` two lines down would resolve the name.
        # Rebind to the reference's own name so downstream hits are labeled
        # consistently and dedup correctly against the reference pass.
        hap_canon = canonical_contig(hap.interval.chrom)
        chrom = next((c for c in reference.contigs if canonical_contig(c) == hap_canon), None)
        if chrom is None:
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
        # Apply the non-clashing subset of the haplotype instead of dropping the
        # whole thing when one variant clashes with the build; record the skipped
        # variants for audit.
        applied_vars, skipped_vars = _partition_variants(ref_seq, start, hap.variants)
        if not applied_vars:
            continue
        edits = [(v.pos, v.ref, v.alt) for v in applied_vars]
        alt_seq = apply_variants(ref_seq, start, edits)
        if alt_seq is None:  # defensive: overlapping applied variants could still clash
            continue
        ref_best = _reference_best(
            scan_sequence(chrom, ref_seq, sp, pam, offset=start, **kw), scorer
        )
        var_spans = [(v.pos, len(v.ref)) for v in applied_vars]
        applied_edits = sorted((v.pos - start, len(v.ref), len(v.alt)) for v in applied_vars)
        # A population "carries" the haplotype only at or above the safety
        # threshold; apply it whether or not the caller restricts the populations
        # (mirrors the population-variant path), and stratify ancestry only over
        # the carrying set so a below-threshold population cannot inflate the
        # per-ancestry off-target burden in ``ancestry_stratification``.
        candidate_pops = populations if populations is not None else hap.populations
        # A population carries the haplotype only if it is *recorded* at/above the
        # threshold. Require presence in ``frequencies``: a ``.get(p, 0.0)`` default
        # would admit an unrecorded population when ``min_freq <= 0`` (0.0 >= 0.0),
        # which then KeyErrors at ``frequencies[p]`` below and, semantically, would
        # claim a population carries a haplotype for which no frequency is known.
        pops = tuple(
            sorted(
                p
                for p in candidate_pops
                if p in hap.frequencies and hap.frequencies[p] >= min_freq
            )
        )
        prov = SiteProvenance(
            origin=SiteOrigin.POPULATION,
            causal_allele=";".join(f"{v.chrom}:{v.pos}:{v.ref}>{v.alt}" for v in applied_vars),
            populations=pops,
            frequency=hap.max_freq(populations),
            ancestries={p: hap.frequencies[p] for p in pops},
            skipped_variants=tuple(f"{v.chrom}:{v.pos}:{v.ref}>{v.alt}" for v in skipped_vars),
        )
        # Scan the alt window in local coordinates, then lift hits back to genomic
        # coordinates through the haplotype's indels so downstream sites are placed
        # correctly (and the ref-vs-alt comparison keys on the true locus).
        alt_local = scan_sequence(chrom, alt_seq, sp, pam, offset=0, **kw)
        for h in _reindex_alt_hits(alt_local, len(ref_seq), start, applied_edits):
            # Attribute the alt hit to the haplotype only if it overlaps one of the
            # applied variants' spans (span, not just the anchor, so a multi-base
            # deletion/MNV whose non-anchor bases reach the window is not dropped).
            if not any(_touches(h, pos, ref_len, pam_len) for pos, ref_len in var_spans):
                continue
            if _strengthens(h, ref_best.get((h.strand, h.start, h.end)), scorer):
                out.append((h, prov))
    return out
