"""The off-target engine: reference + population + haplotype + patient search.

:func:`search` runs the five-stage AlleleForge off-target pipeline and returns an
**ancestry-stratified** :class:`~alleleforge.types.offtarget.OffTargetReport`:

1. **Reference** candidate search (FM-index seed-and-extend in Rust; a correct
   linear-scan fallback here) over the requested regions, both strands.
2. **Population augmentation** — inject gnomAD variants to find *de novo* PAMs
   and seed-mismatch changes a reference-only scan misses.
3. **Haplotype-aware** evaluation — walk the common 1000G/HGDP haplotypes.
4. Optional **patient VCF** pass — personalize off-targets to one genome.
5. **Scoring & aggregation** — CFD + MIT, threshold, de-duplicate, stratify.

Every threshold is a parameter; the defaults are the spec's: ≤4 mismatches,
≤1 DNA + ≤1 RNA bulge, report any site with **CFD ≥ 0.20 or MIT ≥ 0.10**, and
population variants with **MAF ≥ 0.001** in any queried population.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from alleleforge.data.gnomad import GnomadDB
from alleleforge.data.haplotypes import Haplotype
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget._search import Hit, SearchBudget, SiteProvenance, scan_sequence
from alleleforge.offtarget.cache import OffTargetCache, search_signature
from alleleforge.offtarget.haplotype import enumerate_haplotype_sites
from alleleforge.offtarget.population import (
    enumerate_patient_sites,
    enumerate_population_sites,
)
from alleleforge.offtarget.scoring import CfdScorer, OffTargetScorer, mit_score
from alleleforge.types.guide import PAM, Spacer
from alleleforge.types.offtarget import OffTargetReport, OffTargetSite, ScoreMethod, SiteOrigin
from alleleforge.types.sequence import CoordinateSystem, DNASequence, GenomicInterval, Strand
from alleleforge.types.variant import Variant

#: Report any site scoring at or above either threshold (spec defaults).
DEFAULT_CFD_THRESHOLD = 0.20
DEFAULT_MIT_THRESHOLD = 0.10

#: Length of the canonical SpCas9 spacer the MIT score is defined for.
_MIT_LENGTH = 20

#: Auto-engage the FM-index reference path once a region reaches this many bases.
#: Below it the linear scan wins (no index to build/cache); at and above it the
#: content-addressed FM-index seed-and-extend is the genome-scale path. Override
#: per call with ``use_fm_index``.
FM_INDEX_AUTO_THRESHOLD = 1_000_000


def low_stringency_pam(pam: PAM) -> PAM:
    """Broaden a primary PAM to include its low-stringency off-target PAM.

    SpCas9 ``NGG`` broadens to ``NRG`` so the search also anchors on the
    low-stringency ``NAG`` PAM (CFD then down-weights it). Other PAMs are
    returned unchanged.
    """
    return PAM(pattern="NRG") if pam.pattern == "NGG" else pam


def _spacer_str(spacer: Spacer | DNASequence | str) -> str:
    """Return the bare 5'->3' spacer string from any accepted form."""
    if isinstance(spacer, Spacer):
        return str(spacer.sequence)
    return str(spacer)


def _scores(hit: Hit, scorer: OffTargetScorer) -> tuple[float, float]:
    """Return ``(primary_score, mit_score)`` for one hit.

    The MIT score is only defined for an ungapped 20-nt alignment; bulged or
    non-20-nt hits report ``0.0`` for it (and rely on the CFD threshold).
    """
    primary = scorer.score(hit.aligned_spacer, hit.aligned_target, hit.pam_sequence)
    ungapped_20 = (
        hit.dna_bulges == 0 and hit.rna_bulges == 0 and len(hit.aligned_spacer) == _MIT_LENGTH
    )
    mit = mit_score(hit.aligned_spacer, hit.aligned_target) if ungapped_20 else 0.0
    return primary, mit


def _to_site(hit: Hit, prov: SiteProvenance, score: float, method: ScoreMethod) -> OffTargetSite:
    """Build an :class:`OffTargetSite` from a hit and its provenance."""
    locus = GenomicInterval(
        chrom=hit.chrom,
        start=hit.start,
        end=hit.end,
        strand=hit.strand,
        coordinate_system=CoordinateSystem.ZERO_BASED_HALF_OPEN,
    )
    return OffTargetSite(
        locus=locus,
        mismatches=hit.mismatches,
        dna_bulges=hit.dna_bulges,
        rna_bulges=hit.rna_bulges,
        score=score,
        score_method=method,
        origin=prov.origin,
        causal_allele=prov.causal_allele,
        populations=prov.populations,
        frequency=prov.frequency,
        ancestries=prov.ancestries,
    )


def _contig_regions(reference: ReferenceGenome) -> list[GenomicInterval]:
    """Return one plus-strand interval spanning each contig of ``reference``."""
    return [
        GenomicInterval(chrom=c, start=0, end=reference.contig_length(c), strand=Strand.PLUS)
        for c in reference.contigs
    ]


def search(
    spacer: Spacer | DNASequence | str,
    pam: PAM,
    *,
    reference: ReferenceGenome,
    mismatches: int = 4,
    dna_bulges: int = 1,
    rna_bulges: int = 1,
    populations: Sequence[str] | None = None,
    maf: float = 0.001,
    gnomad: GnomadDB | None = None,
    haplotypes: Iterable[Haplotype] = (),
    patient_vcf: Iterable[Variant] | None = None,
    regions: Sequence[GenomicInterval] | None = None,
    scorer: OffTargetScorer | None = None,
    cfd_threshold: float = DEFAULT_CFD_THRESHOLD,
    mit_threshold: float = DEFAULT_MIT_THRESHOLD,
    use_fm_index: bool | None = None,
    cache: OffTargetCache | None = None,
) -> OffTargetReport:
    """Run the full off-target search and return an ancestry-stratified report.

    Args:
        spacer: The on-target guide spacer, 5'->3'.
        pam: The primary PAM (e.g. ``NGG``); broadened internally to include the
            low-stringency PAM for the search.
        reference: The reference genome.
        mismatches: Maximum base mismatches (default 4).
        dna_bulges: Maximum DNA bulges (default 1).
        rna_bulges: Maximum RNA bulges (default 1).
        populations: Ancestry labels to query/stratify (default: each source's).
        maf: Minimum population allele frequency to include (default 0.001).
        gnomad: gnomAD database for population augmentation (optional).
        haplotypes: Common haplotypes for haplotype-aware search (optional).
        patient_vcf: Personal variants to personalize the search (optional).
        regions: Restrict the search to these intervals; defaults to every contig.
        scorer: The primary specificity scorer (default :class:`CfdScorer`).
        cfd_threshold: Report a site at or above this CFD (default 0.20).
        mit_threshold: ...or at or above this MIT (default 0.10).
        use_fm_index: Force (``True``) or forbid (``False``) the FM-index
            seed-and-extend reference path; ``None`` (default) auto-engages it per
            region once the region reaches :data:`FM_INDEX_AUTO_THRESHOLD` bases.
            The path returns identical hits to the linear scan (a parity test
            pins this); it is the cached, content-addressed genome-scale path.
        cache: Optional cross-run :class:`OffTargetCache`. Used **only** when the
            result is a pure function of the reference — the default scorer and no
            gnomAD/haplotype/patient augmentation — so a stale entry can never be
            served for a query whose external data the key does not capture.

    Returns:
        An :class:`OffTargetReport`, sorted by descending score and
        ancestry-stratified by default.
    """
    sp = _spacer_str(spacer)
    primary = scorer if scorer is not None else CfdScorer()
    scan_pam = low_stringency_pam(pam)
    search_regions = list(regions) if regions is not None else _contig_regions(reference)
    haplotype_list = list(haplotypes)
    kw: SearchBudget = {
        "mismatches": mismatches,
        "dna_bulges": dna_bulges,
        "rna_bulges": rna_bulges,
    }

    # The cache is safe only for a reference-only search with the default scorer:
    # population/haplotype/patient augmentation depends on data the key can't fully
    # capture, and a custom scorer changes scores the signature does not see.
    cache_eligible = (
        cache is not None
        and scorer is None
        and gnomad is None
        and not haplotype_list
        and patient_vcf is None
    )
    signature: str | None = None
    if cache is not None and cache_eligible:
        signature = search_signature(
            sp,
            pam,
            reference=reference,
            mismatches=mismatches,
            dna_bulges=dna_bulges,
            rna_bulges=rna_bulges,
            cfd_threshold=cfd_threshold,
            mit_threshold=mit_threshold,
            regions=search_regions,
        )
        cached = cache.get(signature)
        if cached is not None:
            return cached

    tagged: list[tuple[Hit, SiteProvenance]] = []
    ref_prov = SiteProvenance(origin=SiteOrigin.REFERENCE)

    # Stage 1 — reference candidate search. The FM-index seed-and-extend is the
    # genome-scale path: auto-engaged per region past FM_INDEX_AUTO_THRESHOLD
    # bases unless the caller forces it on or off.
    for region in search_regions:
        seq = str(reference.fetch(region.model_copy(update={"strand": Strand.PLUS})))
        fm = use_fm_index if use_fm_index is not None else len(seq) >= FM_INDEX_AUTO_THRESHOLD
        for hit in scan_sequence(
            region.chrom, seq, sp, scan_pam, offset=region.start, use_fm_index=fm, **kw
        ):
            tagged.append((hit, ref_prov))

    # Stage 2 — population augmentation (gnomAD de-novo PAM / seed changes).
    if gnomad is not None:
        for region in search_regions:
            variants = gnomad.frequencies(region, populations=populations, maf=maf)
            tagged.extend(
                enumerate_population_sites(
                    sp,
                    scan_pam,
                    reference=reference,
                    variants=variants,
                    populations=populations,
                    maf=maf,
                    **kw,
                )
            )

    # Stage 3 — haplotype-aware evaluation.
    tagged.extend(
        enumerate_haplotype_sites(
            sp,
            scan_pam,
            reference=reference,
            haplotypes=haplotype_list,
            populations=populations,
            min_freq=maf,
            **kw,
        )
    )

    # Stage 4 — optional patient-VCF personalization.
    if patient_vcf is not None:
        tagged.extend(
            enumerate_patient_sites(sp, scan_pam, reference=reference, variants=patient_vcf, **kw)
        )

    # Stage 5 — score, threshold, de-duplicate, sort.
    best: dict[tuple[str, int, int, Strand], OffTargetSite] = {}
    for hit, prov in tagged:
        cfd, mit = _scores(hit, primary)
        if cfd < cfd_threshold and mit < mit_threshold:
            continue
        site = _to_site(hit, prov, cfd, primary.method)
        key = (hit.chrom, hit.start, hit.end, hit.strand)
        existing = best.get(key)
        if existing is None or site.score > existing.score:
            best[key] = site

    sites = tuple(sorted(best.values(), key=lambda s: s.score, reverse=True))
    report = OffTargetReport(
        spacer=sp,
        pam=pam.pattern,
        sites=sites,
        mismatch_threshold=mismatches,
        reference_build=reference.build or "hg38",
    )
    if cache is not None and signature is not None:
        cache.put(signature, report)
    return report
