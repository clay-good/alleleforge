"""Population-variant augmentation of the off-target search.

Reference-genome-only off-target analysis is a known safety blind spot: a minor
allele can create a *de novo* PAM, or remove a seed mismatch, yielding an
off-target a reference scan never sees. This module re-scans the neighborhood of
each candidate variant on its **alternate** allele and reports any PAM-anchored
hit that the variant *creates* or *strengthens* relative to the reference,
annotated with the causal allele, the populations carrying it, and the frequency.

This reproduces the published reference-bias finding (Cancellieri, Pinello et
al., *Nat Genet* 2023): the BCL11A enhancer variant ``rs114518452`` creates a
de-novo ``NGG`` PAM that yields a high-CFD off-target, enriched in African-ancestry
populations — invisible to a reference-only scan.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from alleleforge.data.gnomad import PopulationFrequency
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget._search import Hit, SiteProvenance, scan_sequence
from alleleforge.types.guide import PAM
from alleleforge.types.offtarget import SiteOrigin
from alleleforge.types.sequence import CoordinateSystem, DNASequence, GenomicInterval, Strand
from alleleforge.types.variant import Variant


def _apply(seq: str, rel: int, ref: str, alt: str) -> str:
    """Return ``seq`` with ``ref`` at offset ``rel`` replaced by ``alt``."""
    return seq[:rel] + alt + seq[rel + len(ref) :]


def _touches(hit: Hit, pos: int, pam_len: int) -> bool:
    """Return ``True`` if ``pos`` lies in the hit's protospacer-or-PAM span."""
    return hit.start - pam_len <= pos < hit.end + pam_len


def _variant_window_hits(
    spacer: str,
    pam: PAM,
    reference: ReferenceGenome,
    *,
    chrom: str,
    pos: int,
    ref: str,
    alt: str,
    mismatches: int,
    dna_bulges: int,
    rna_bulges: int,
) -> list[Hit]:
    """Return alt-allele hits the variant creates or strengthens vs. reference.

    Scans a window around the variant on both the reference and the alternate
    allele; an alt hit is attributed to the variant when it overlaps the variant
    locus and has no reference hit at the same placement with as few edits.
    """
    if chrom not in reference.contigs:
        return []
    margin = len(spacer) + len(pam.pattern) + 1
    start = max(0, pos - margin)
    end = pos + len(ref) + margin
    fetched = reference.fetch_result(
        GenomicInterval(
            chrom=chrom,
            start=start,
            end=end,
            strand=Strand.PLUS,
            coordinate_system=CoordinateSystem.ZERO_BASED_HALF_OPEN,
        )
    )
    ref_seq = str(fetched.sequence)
    rel = pos - start
    if ref_seq[rel : rel + len(ref)].upper() != ref.upper():
        return []  # the variant's ref does not match this build; skip safely
    alt_seq = _apply(ref_seq, rel, ref, alt)

    kw = {"mismatches": mismatches, "dna_bulges": dna_bulges, "rna_bulges": rna_bulges}
    ref_edits: dict[tuple[Strand, int, int], int] = {}
    for h in scan_sequence(chrom, ref_seq, spacer, pam, offset=start, **kw):
        key = (h.strand, h.start, h.end)
        ref_edits[key] = min(ref_edits.get(key, h.edits), h.edits)

    created: list[Hit] = []
    for h in scan_sequence(chrom, alt_seq, spacer, pam, offset=start, **kw):
        if not _touches(h, pos, len(pam.pattern)):
            continue
        prior = ref_edits.get((h.strand, h.start, h.end))
        if prior is None or h.edits < prior:
            created.append(h)
    return created


def enumerate_population_sites(
    spacer: str | DNASequence,
    pam: PAM,
    *,
    reference: ReferenceGenome,
    variants: Iterable[PopulationFrequency],
    populations: Sequence[str] | None = None,
    maf: float = 0.001,
    mismatches: int = 4,
    dna_bulges: int = 1,
    rna_bulges: int = 1,
) -> list[tuple[Hit, SiteProvenance]]:
    """Enumerate off-target hits created or strengthened by population variants.

    Args:
        spacer: The on-target guide spacer, 5'->3'.
        pam: The PAM pattern to anchor on (broaden to include low-stringency
            PAMs, e.g. ``NRG`` for SpCas9 ``NGG``+``NAG``).
        reference: The reference genome.
        variants: Candidate population variants (e.g. from ``GnomadDB``).
        populations: Ancestry labels to consider; ``None`` uses each variant's.
        maf: Minimum allele frequency in any queried population to include.
        mismatches: Maximum base mismatches.
        dna_bulges: Maximum DNA bulges.
        rna_bulges: Maximum RNA bulges.

    Returns:
        ``(hit, provenance)`` pairs with ``provenance.origin = POPULATION``.
    """
    sp = str(spacer).upper()
    out: list[tuple[Hit, SiteProvenance]] = []
    for var in variants:
        pops = list(populations) if populations is not None else list(var.populations)
        ancestries = {p: var.populations.get(p, 0.0) for p in pops}
        carrying = tuple(sorted(p for p in pops if ancestries[p] >= maf))
        if not carrying:
            continue
        frequency = max((ancestries[p] for p in carrying), default=var.overall_af)
        hits = _variant_window_hits(
            sp,
            pam,
            reference,
            chrom=var.chrom,
            pos=var.pos,
            ref=var.ref,
            alt=var.alt,
            mismatches=mismatches,
            dna_bulges=dna_bulges,
            rna_bulges=rna_bulges,
        )
        prov = SiteProvenance(
            origin=SiteOrigin.POPULATION,
            causal_allele=var.variant_key,
            populations=carrying,
            frequency=frequency,
            ancestries={p: ancestries[p] for p in carrying},
        )
        out.extend((h, prov) for h in hits)
    return out


def enumerate_patient_sites(
    spacer: str | DNASequence,
    pam: PAM,
    *,
    reference: ReferenceGenome,
    variants: Iterable[Variant],
    mismatches: int = 4,
    dna_bulges: int = 1,
    rna_bulges: int = 1,
) -> list[tuple[Hit, SiteProvenance]]:
    """Enumerate off-target hits created or strengthened by a patient's variants.

    Identical to :func:`enumerate_population_sites` but for personal variants
    from a supplied VCF; the provenance origin is ``PATIENT`` and carries no
    population frequency.
    """
    sp = str(spacer).upper()
    out: list[tuple[Hit, SiteProvenance]] = []
    for var in variants:
        hits = _variant_window_hits(
            sp,
            pam,
            reference,
            chrom=var.chrom,
            pos=var.pos,
            ref=var.ref,
            alt=var.alt,
            mismatches=mismatches,
            dna_bulges=dna_bulges,
            rna_bulges=rna_bulges,
        )
        prov = SiteProvenance(origin=SiteOrigin.PATIENT, causal_allele=str(var))
        out.extend((h, prov) for h in hits)
    return out
