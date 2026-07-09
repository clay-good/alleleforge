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
from alleleforge.offtarget._search import (
    Hit,
    SearchBudget,
    SiteProvenance,
    _reindex_alt_hits,
    scan_sequence,
)
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


def _apply(seq: str, rel: int, ref: str, alt: str) -> str:
    """Return ``seq`` with ``ref`` at offset ``rel`` replaced by ``alt``."""
    return seq[:rel] + alt + seq[rel + len(ref) :]


def _touches(hit: Hit, pos: int, pam_len: int) -> bool:
    """Return ``True`` if ``pos`` lies in the hit's protospacer-or-PAM span."""
    return hit.start - pam_len <= pos < hit.end + pam_len


#: The strongest reference hit at a placement: ``(best specificity score, fewest edits)``.
ReferenceBest = tuple[float, int]


def _reference_best(
    hits: list[Hit], scorer: OffTargetScorer
) -> dict[tuple[Strand, int, int], ReferenceBest]:
    """Return the best reference ``(score, edits)`` per placement over ``hits``."""
    best: dict[tuple[Strand, int, int], ReferenceBest] = {}
    for h in hits:
        key = (h.strand, h.start, h.end)
        bulged = h.dna_bulges > 0 or h.rna_bulges > 0
        s = scorer.score(h.aligned_spacer, h.aligned_target, h.pam_sequence, bulged=bulged)
        prev = best.get(key)
        best[key] = (max(s, prev[0]), min(h.edits, prev[1])) if prev is not None else (s, h.edits)
    return best


def _strengthens(hit: Hit, prior: ReferenceBest | None, scorer: OffTargetScorer) -> bool:
    """Return whether an alt ``hit`` is created or strengthens the reference.

    An alt hit is nominated when it is **created** (no reference hit at the same
    placement) or **more dangerous** than the best reference hit there by *either*
    measure: a strictly higher specificity score (catches a PAM upgrade such as
    ``NAG``→``NGG`` that leaves the edit count unchanged), or strictly fewer edits
    (catches a variant that removes a mismatch or bulge — a real strengthening the
    bulge-blind CFD score alone would miss). The union is the safety-maximizing
    gate: it never drops a hit that either signal flags.
    """
    if prior is None:
        return True
    prior_score, prior_edits = prior
    bulged = hit.dna_bulges > 0 or hit.rna_bulges > 0
    alt_score = scorer.score(
        hit.aligned_spacer, hit.aligned_target, hit.pam_sequence, bulged=bulged
    )
    return alt_score > prior_score or hit.edits < prior_edits


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
    scorer: OffTargetScorer,
) -> list[Hit]:
    """Return alt-allele hits the variant creates or strengthens vs. reference.

    Scans a window around the variant on both the reference and the alternate
    allele; an alt hit is attributed to the variant when it overlaps the variant
    locus and is **more dangerous** than any reference hit at the same placement,
    judged by the specificity score (``scorer``), not merely by a lower edit count.
    A minor allele that upgrades a weak PAM (e.g. ``NAG``→``NGG``) raises the score
    at an unchanged edit count, so scoring the comparison — not counting edits —
    catches the strengthened site the edit-count gate would silently drop.
    """
    # Reconcile the variant's contig name against the reference's naming style
    # ("1" vs "chr1") so a naming mismatch does not silently drop the variant
    # (`fetch_result` below reconciles the name, so the raw membership guard
    # contradicted its own downstream behavior). Rebind to the reference's name
    # for consistent hit labeling and dedup.
    matched = next(
        (c for c in reference.contigs if canonical_contig(c) == canonical_contig(chrom)),
        None,
    )
    if matched is None:
        return []
    chrom = matched
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

    kw: SearchBudget = {
        "mismatches": mismatches,
        "dna_bulges": dna_bulges,
        "rna_bulges": rna_bulges,
    }
    # Best reference (specificity score, min edits) per placement. An alt hit is
    # nominated when it beats the strongest reference hit at the same locus by
    # *either* measure — see :func:`_strengthens`.
    ref_hits = scan_sequence(chrom, ref_seq, spacer, pam, offset=start, **kw)
    ref_best = _reference_best(ref_hits, scorer)

    # Scan the alt allele in window-local coordinates, then lift every hit back to
    # true genomic coordinates through the (possibly length-changing) edit, so an
    # insertion or deletion places downstream hits correctly and the ref-vs-alt
    # comparison below keys on the same genomic locus for a pre-existing site.
    applied = [(rel, len(ref), len(alt))]
    alt_local = scan_sequence(chrom, alt_seq, spacer, pam, offset=0, **kw)
    created: list[Hit] = []
    for h in _reindex_alt_hits(alt_local, len(ref_seq), start, applied):
        if not _touches(h, pos, len(pam.pattern)):
            continue
        if _strengthens(h, ref_best.get((h.strand, h.start, h.end)), scorer):
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
    scorer: OffTargetScorer | None = None,
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
        scorer: The specificity scorer used to judge whether an alt hit strengthens
            a reference hit at the same placement (default :class:`CfdScorer`); pass
            the engine's primary scorer so nomination and reporting agree.

    Returns:
        ``(hit, provenance)`` pairs with ``provenance.origin = POPULATION``.
    """
    sp = str(spacer).upper()
    scorer = scorer if scorer is not None else CfdScorer()
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
            scorer=scorer,
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
    scorer: OffTargetScorer | None = None,
) -> list[tuple[Hit, SiteProvenance]]:
    """Enumerate off-target hits created or strengthened by a patient's variants.

    Identical to :func:`enumerate_population_sites` but for personal variants
    from a supplied VCF; the provenance origin is ``PATIENT`` and carries no
    population frequency.
    """
    sp = str(spacer).upper()
    scorer = scorer if scorer is not None else CfdScorer()
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
            scorer=scorer,
        )
        prov = SiteProvenance(origin=SiteOrigin.PATIENT, causal_allele=str(var))
        out.extend((h, prov) for h in hits)
    return out
