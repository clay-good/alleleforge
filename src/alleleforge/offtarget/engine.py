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

from collections import defaultdict
from collections.abc import Iterable, Sequence
from typing import Any

from alleleforge import _native
from alleleforge.data.gnomad import GnomadDB
from alleleforge.data.haplotypes import Haplotype
from alleleforge.genome.index import GenomeIndex
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget._bounds import reject_non_finite
from alleleforge.offtarget._counts import SourceCounts
from alleleforge.offtarget._search import (
    Hit,
    SearchBudget,
    SiteProvenance,
    check_bulge_budget,
    scan_sequence,
)
from alleleforge.offtarget.cache import OffTargetCache, search_signature
from alleleforge.offtarget.haplotype import enumerate_haplotype_sites
from alleleforge.offtarget.population import (
    enumerate_patient_sites,
    enumerate_population_sites,
)
from alleleforge.offtarget.scoring import CfdScorer, OffTargetScorer, mit_score
from alleleforge.types.guide import PAM, Spacer
from alleleforge.types.offtarget import OffTargetReport, OffTargetSite, ScoreMethod, SiteOrigin
from alleleforge.types.sequence import (
    IUPAC_ALPHABET,
    CoordinateSystem,
    DNASequence,
    GenomicInterval,
    Strand,
    canonical_contig,
)
from alleleforge.types.variant import Variant, assembly_matches

#: Report any site scoring at or above either threshold.
#:
#: **Project defaults, not published cutoffs.** No threshold separates a real
#: off-target from an irrelevant one — CFD and MIT are continuous estimates — and these
#: are set where a site stops being one of very many weak alignments and becomes worth
#: a reader's attention. They are the most consequential numbers in the engine, because
#: a site below them is not merely deprioritised, it is *absent* from the report; that
#: is why every report states them inline ("sites reported at CFD >= 0.20 or MIT >=
#: 0.10") rather than leaving a count to be read as absolute. Both are per-call
#: overridable, and lowering them only ever adds sites.
DEFAULT_CFD_THRESHOLD = 0.20

#: The MIT companion to the CFD threshold above, and a project default on the same
#: terms: not a published cutoff, stated inline in every report, per-call overridable,
#: and lowering it only ever adds sites.
DEFAULT_MIT_THRESHOLD = 0.10

#: Length of the canonical SpCas9 spacer the MIT score is defined for.
_MIT_LENGTH = 20

#: The FM-index reference path is **opt-in**, never automatic. It used to engage
#: itself once a region reached 1,000,000 bases, on the stated grounds that the index
#: build "only amortizes at contig scale". Measured, on this machine, with the native
#: crate present and comparing the default path against a forced linear scan:
#:
#:     1 Mb, one guide     linear  1.77s   auto/FM   4.85s   (2.7x slower)
#:     2 Mb, one guide     linear  3.61s   auto/FM   9.69s   (2.7x slower)
#:     8 Mb, one guide     linear 14.22s   auto/FM  65.19s   (4.6x slower)
#:     1 Mb, five guides   linear  9.75s   auto/FM  21.56s   (2.2x slower)
#:
#: The justification was backwards: it does not converge at contig scale, it diverges,
#: and it does not amortize across guides either. So the threshold turned the *default*
#: configuration 2.7x slower at exactly the genome scale the tool exists for, and worse
#: from there. `scripts/native_speedup.py` has been printing "SLOWER" for this pair; the
#: number was in the output and the decision was in the prose.
#:
#: The path itself stays — it is exact, parity-pinned, and a caller with a prebuilt
#: memory-mapped index may have reasons of their own (memory, not time). It is reached
#: by asking: `use_fm_index=True`, or by supplying `genome_index=`.
#:
#: Not measured, and so not claimed either way: a persistent cross-process index whose
#: build cost is fully paid in an earlier run. The speedup script prebuilds the index
#: outside its timing and still measures the FM *queries* 11-14x slower than the linear
#: scan, which is the reason to doubt that case too, but it was not measured here.
FM_INDEX_AUTO_ENGAGES = False


def low_stringency_pam(pam: PAM) -> PAM:
    """Broaden a primary PAM to include its low-stringency off-target PAM.

    SpCas9 ``NGG`` broadens to ``NRG`` so the search also anchors on the
    low-stringency ``NAG`` PAM (CFD then down-weights it). Other PAMs are
    returned unchanged.
    """
    return PAM(pattern="NRG") if pam.pattern == "NGG" else pam


def _spacer_str(spacer: Spacer | DNASequence | str) -> str:
    """Return the bare 5'->3' spacer string, refusing one outside the IUPAC alphabet.

    A `Spacer` and a `DNASequence` are validated by construction; a bare ``str`` was
    not, and both shells hand this one. So `--pam NZZ` was refused by name while
    ``aforge offtarget '>chr1'`` — a pasted FASTA header — was *scanned*, reported as
    "ambiguous at position(s) 1, 3, 4, 5" (``>``, ``h``, ``r``, ``1`` are not ambiguity
    codes, they are not bases) and given ``specificity 0.026`` over a 5,072-placement
    sub-threshold tail. `POST /api/offtarget` accepted the same string. A safety number
    computed from a typo and printed without a refusal is the failure this project keeps
    finding, and here the alphabet rule was enforced on one argument of the same call
    and not the other.

    Validated here rather than in each shell: `search` is the one door every caller
    goes through, and a check at the shells is one a future caller can walk past.
    ``N`` and the other IUPAC ambiguity codes stay accepted — they are what the
    "ambiguous at position(s)" disclosure exists for.

    Raises:
        ValueError: If ``spacer`` is empty, or holds a character outside the IUPAC
            alphabet. Both shells already turn this into their own refusal.
    """
    if isinstance(spacer, Spacer):
        return str(spacer.sequence)
    if isinstance(spacer, DNASequence):
        return str(spacer)
    text = str(spacer)
    if not text.strip():
        # Round 523 chose to *label* a too-short query rather than refuse it: screening a
        # seed sequence is a legitimate thing to ask for. An empty spacer is not that —
        # there is nothing to screen. It matched at every position of the genome, so a
        # blank field or an unset shell variable produced the most alarming report this
        # tool can emit: thousands of "off-target sites", worst score 1.000, specificity
        # 0.000. Refused, because no caveat makes that report mean anything.
        raise ValueError(
            "the spacer is empty — there is nothing to search for. Every position of "
            "the genome matches an empty query, which is why this produced a specificity "
            "of zero rather than an error. Supply the guide's protospacer (typically 20 "
            "nt, 5'->3', without the PAM)."
        )
    stray = sorted(set(text.upper()) - IUPAC_ALPHABET)
    if stray:
        raise ValueError(
            f"spacer has non-IUPAC characters: {stray} — a spacer is DNA (ACGT plus the "
            "IUPAC ambiguity codes); check for a pasted FASTA header, a stray space or "
            "a digit"
        )
    return text


def _scores(hit: Hit, scorer: OffTargetScorer) -> tuple[float, float | None]:
    """Return ``(primary_score, mit_score)`` for one hit.

    The MIT score is only defined for an ungapped 20-nt alignment; bulged or
    non-20-nt hits report ``None`` for it (and rely on the CFD threshold). For
    thresholding, an undefined MIT is treated as ``0.0`` (it cannot clear a
    positive MIT threshold), so selection is unchanged; the ``None`` is preserved
    on the site to record that MIT does not apply, rather than implying a real 0.
    """
    bulged = hit.dna_bulges > 0 or hit.rna_bulges > 0
    primary = scorer.score(hit.aligned_spacer, hit.aligned_target, hit.pam_sequence, bulged=bulged)
    ungapped_20 = not bulged and len(hit.aligned_spacer) == _MIT_LENGTH
    mit = mit_score(hit.aligned_spacer, hit.aligned_target) if ungapped_20 else None
    return primary, mit


def _site_matrix(hit: Hit, scorer: OffTargetScorer) -> str | None:
    """Return the matrix identity the scorer actually used for this hit.

    A scorer may fall back off its nominal matrix for an off-length alignment
    (the published CFD matrix is 20-nt-only, so a bulge-collapsed hit is scored by
    the length-relative approximation). When the scorer exposes ``matrix_for`` we
    record that per-call identity, so an off-length score is never labeled as the
    published matrix; otherwise we record the scorer's static matrix.
    """
    matrix_for = getattr(scorer, "matrix_for", None)
    if matrix_for is not None:
        bulged = hit.dna_bulges > 0 or hit.rna_bulges > 0
        result: str = matrix_for(hit.aligned_spacer, hit.aligned_target, bulged=bulged)
        return result
    matrix: str | None = getattr(scorer, "matrix", None)
    return matrix


def _to_site(
    hit: Hit,
    prov: SiteProvenance,
    score: float,
    method: ScoreMethod,
    mit: float | None = None,
    matrix: str | None = None,
) -> OffTargetSite:
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
        mit_score=mit,
        origin=prov.origin,
        causal_allele=prov.causal_allele,
        populations=prov.populations,
        frequency=prov.frequency,
        ancestries=prov.ancestries,
        score_matrix=matrix,
        pam_sequence=hit.pam_sequence,
    )


#: The one-pass native form of the count below, when the crate is built. Resolved once
#: at import, like the scan's other kernels: this runs once per sequence per search, so
#: the dispatch is not hot, but the pattern is the one every kernel here follows.
_NATIVE_RESOLVED_BASE_COUNT = (
    getattr(_native._ext, "resolved_base_count", None)  # type: ignore[attr-defined]
    if _native.NATIVE_AVAILABLE
    else None
)


class RunScanner:
    """One design's off-target scans, run at most once per (spacer, excluded locus).

    Every vertical calls :func:`search` with the same ten run-wide arguments — the
    reference, the population and haplotype sources, the patient VCF, the region
    restriction, the two reuse stores — and varies two: which spacer, and which locus to
    exclude from its own report. Binding the ten and memoizing on the two is what stops a
    design scanning the same genome for the same spacer more than once.

    That was happening in two of the three verticals. Prime memoizes its *merged* report
    under the pegRNA pair, so a peg spacer paired with two nicking guides was scanned
    twice; the base-editor vertical scans per window, and two deaminases over one
    protospacer are two windows with one spacer. Measured: 1 of 6, 4 of 10 and 1 of 4
    scans on three prime loci, 1 of 2 on a base-editor locus, and 81 scans where 56
    distinct ones exist across a ten-variant cohort. A scan is a pass over the whole
    genome — the dominant cost of a run.

    The key is exactly what a report depends on. It carries the spacer's own locus
    *excluded* from it, so two pegRNAs at different loci with one spacer must not share a
    report: keying on the spacer alone would hand one of them a report that excluded the
    other's locus and drop a genuine paralogous off-target for it.
    """

    def __init__(self, **run_arguments: Any) -> None:
        """Bind the run-wide arguments every scan in this design shares."""
        self._arguments = run_arguments
        self._scans: dict[tuple[str, str | None], OffTargetReport] = {}

    def scan(self, spacer: Spacer, pam: PAM, on_target: GenomicInterval | None) -> OffTargetReport:
        """Return the report for ``spacer``, running the scan only the first time."""
        key = (str(spacer.sequence), str(on_target) if on_target is not None else None)
        hit = self._scans.get(key)
        if hit is not None:
            return hit
        report = search(spacer, pam, on_target=on_target, **self._arguments)
        self._scans[key] = report
        return report

    def __len__(self) -> int:
        """Return how many distinct scans this design has run."""
        return len(self._scans)


def _resolved_base_count(sequence: str) -> int:
    """Return how many bases of ``sequence`` are unambiguous A/C/G/T.

    Counted without upper-casing first. ``sequence.upper()`` allocates a full copy of
    the region — on a whole chromosome a ~250 MB transient on top of the sequence
    already held, in a path whose design is explicitly bounded-memory — to save ~8% of
    a step that is negligible beside the scan (measured on 20 Mb: +20 MB peak, 140 ms
    vs 151 ms).

    Both cases are counted even though sequence arrives upper-cased today. That
    normalization is ``pyfaidx``'s ``sequence_always_upper=True``, a *dependency
    default* rather than an invariant of this repository; if it changed, every base of
    a repeat-masked genome would count as unsearchable and the report would claim a
    real scan had covered almost nothing — the false alarm exactly inverse to the one
    this count exists to raise. Eight ``str.count`` passes instead of four is not a
    price worth arguing about against that.

    It is a named function rather than an inline expression so it can be tested: with
    the reference normalizing case on the way out, no end-to-end fixture can reach the
    lowercase path.

    The native kernel does the same count in one pass, also without copying, and is used
    when the crate is built — "eight passes are negligible beside the scan" was measured
    against a scan several rounds slower than today's, and the eight passes had grown to
    a fifth of it.
    """
    if _NATIVE_RESOLVED_BASE_COUNT is not None:  # pragma: no cover - native not built in CI
        counted: int = _NATIVE_RESOLVED_BASE_COUNT(sequence)
        return counted
    return sum(sequence.count(base) for base in "ACGTacgt")


def _is_on_target(hit: Hit, on_target: GenomicInterval | None) -> bool:
    """Return whether ``hit`` is the guide's own intended on-target locus.

    The reference always contains the guide's own protospacer, so a genome-wide
    scan nominates it as a perfect (score 1.0) match. It is the *intended* target,
    not an off-target: the Hsu/CRISPOR aggregate specificity score excludes it, and
    counting it would peg every guide's worst-case score at 1.0 (inert safety axis)
    and cap :meth:`OffTargetReport.specificity_score` at 0.5 for even a perfectly
    clean guide. A caller that knows the on-target placement passes it so this one
    locus is dropped — a *paralogous* perfect match at any **other** locus is a real
    off-target and is kept. Matching is naming-aware on the contig.

    An exact-interval test is not enough, and the gap was not hypothetical. With
    bulges allowed, the guide also aligns to **its own locus** one base short: a
    20-nt spacer matching a 19-nt window through a single bulge, zero mismatches,
    score 1.0, at an interval that differs from the placement by exactly the bulge.
    On a realistic prime menu that self-match survived on 170 of 470 candidates,
    halving each one's specificity and pegging the cohort's worst-off-target column
    at 1.0 — the precise failure this function exists to prevent, arriving through
    the one alignment class it did not consider.

    So a **bulged** hit also counts as on-target when it lies inside the placement
    grown by the bulge budget on each side. The containment test keeps the original
    guarantee intact: a paralog *abutting* the on-target is outside that window and
    survives, and an un-bulged hit is only ever excluded on an exact interval match,
    since with no bulge a different start is genuinely a different protospacer.
    """
    if on_target is None:
        return False
    if canonical_contig(hit.chrom) != canonical_contig(on_target.chrom):
        return False
    if hit.strand != on_target.strand:
        return False
    # Containment in the placement grown by this hit's own bulge budget. An un-bulged
    # hit has slack 0, so this reduces to the exact-interval test it replaces: with no
    # bulge the alignment is the spacer's full length, and a window of that length
    # contained in the placement *is* the placement. No separate zero-bulge branch is
    # needed, and adding one would only be a branch nothing can distinguish.
    slack = hit.dna_bulges + hit.rna_bulges
    return on_target.start - slack <= hit.start and hit.end <= on_target.end + slack


def _in_regions(hit: Hit, regions: Sequence[GenomicInterval]) -> bool:
    """Return whether ``hit``'s locus overlaps any of ``regions`` (naming-aware)."""
    locus = GenomicInterval(
        chrom=hit.chrom,
        start=hit.start,
        end=hit.end,
        strand=hit.strand,
        coordinate_system=CoordinateSystem.ZERO_BASED_HALF_OPEN,
    )
    return any(locus.overlaps(region) for region in regions)


def _contig_regions(reference: ReferenceGenome) -> list[GenomicInterval]:
    """Return one plus-strand interval spanning each contig of ``reference``."""
    return [
        GenomicInterval(chrom=c, start=0, end=reference.contig_length(c), strand=Strand.PLUS)
        for c in reference.contigs
    ]


def _is_whole_contig(
    region: GenomicInterval, reference: ReferenceGenome, genome_index: GenomeIndex
) -> bool:
    """Return whether ``region`` is exactly an indexed whole contig.

    The persistent index is built per whole contig, so its coordinates only line
    up with a region that spans the entire contig (a sub-region would need its own
    index). Anything else falls back to the per-call build.
    """
    return (
        region.chrom in genome_index.contigs
        and region.start == 0
        and region.end == reference.contig_length(region.chrom)
    )


def _reject_unknown_contigs(regions: Sequence[GenomicInterval], reference: ReferenceGenome) -> None:
    """Raise if any region names a contig ``reference`` does not have.

    Raises:
        ValueError: naming the offending contig and what the reference does have.
            Deliberately not a `KeyError` from the fetch: the caller's mistake is the
            *region list*, and the fix is usually the panel's assembly or its `chr`
            prefixing, neither of which a bare missing-key error suggests.
    """
    if not regions:
        return
    known = {canonical_contig(c) for c in reference.contigs}
    for region in regions:
        if canonical_contig(region.chrom) not in known:
            available = ", ".join(sorted(reference.contigs)[:8])
            more = "…" if len(reference.contigs) > 8 else ""
            raise ValueError(
                f"region {region} names contig {region.chrom!r}, which this reference "
                f"does not have (it has: {available}{more}). Check the panel's assembly "
                "and contig naming — a dropped region searches less than you asked for."
            )


def _rename_to_reference(
    regions: Sequence[GenomicInterval], reference: ReferenceGenome
) -> list[GenomicInterval]:
    """Return ``regions`` with each contig renamed to the reference's own spelling.

    Every coordinate this search reports describes a position *in the reference*, and
    the only name guaranteed to address that position in that reference is the
    reference's own. Reported sites inherit their contig from the region they were
    found in, so without this the same site in the same genome was called
    ``chr2:43-63`` when unscoped (contigs came from the reference) and ``2:43-63``
    when scoped with ``--region 2:0-183`` — the identity of a result depending on an
    unrelated scoping flag, and two runs producing site lists that do not join.

    The rename is always *toward* the supplied genome, so a bare-named FASTA yields
    bare-named output. `canonical_contig` already reconciles the styles for lookup, so
    this changes only what is written down; `_reject_unknown_contigs` has already
    refused anything that does not reconcile at all.

    Args:
        regions: The search scope, in whatever spelling the caller used.
        reference: The genome being searched.

    Returns:
        The same intervals, named as the reference names them.
    """
    by_canonical = {canonical_contig(c): c for c in reference.contigs}
    return [
        region
        if by_canonical.get(canonical_contig(region.chrom), region.chrom) == region.chrom
        else region.model_copy(update={"chrom": by_canonical[canonical_contig(region.chrom)]})
        for region in regions
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
    on_target: GenomicInterval | None = None,
    scorer: OffTargetScorer | None = None,
    cfd_threshold: float = DEFAULT_CFD_THRESHOLD,
    mit_threshold: float = DEFAULT_MIT_THRESHOLD,
    use_fm_index: bool | None = None,
    cache: OffTargetCache | None = None,
    genome_index: GenomeIndex | None = None,
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
        on_target: The guide's own intended protospacer locus. When given, the site
            at exactly this locus (the guide's perfect self-match, which the
            reference always contains) is excluded from the report — it is the
            intended target, not an off-target, and the Hsu/CRISPOR aggregate
            excludes it. A paralogous perfect match at any other locus is kept.
            Omitted (``None``) for a bare off-target scan, which reports the
            on-target like any other match.
        scorer: The primary specificity scorer (default :class:`CfdScorer`).
        cfd_threshold: Report a site at or above this CFD (default 0.20).
        mit_threshold: ...or at or above this MIT (default 0.10).
        use_fm_index: Force (``True``) or forbid (``False``) the FM-index
            seed-and-extend reference path. ``None`` (default) takes the linear scan
            at every size — see :data:`FM_INDEX_AUTO_ENGAGES` for the measurements
            that removed the automatic threshold. The path returns identical hits
            either way (a parity test pins this); what differs is only the time.
        cache: Optional cross-run :class:`OffTargetCache`. Used **only** when the
            result is a pure function of the reference — the default scorer and no
            gnomAD/haplotype/patient augmentation — so a stale entry can never be
            served for a query whose external data the key does not capture.
        genome_index: Optional persistent, memory-mapped :class:`GenomeIndex`. When
            given, a whole-contig reference scan anchors PAMs through it instead of
            rebuilding an in-memory index — identical hits (a parity test pins this),
            but the (expensive) index is built once and reused across runs/guides.

    Returns:
        An :class:`OffTargetReport`, sorted by descending score and
        ancestry-stratified by default.

    Raises:
        ValueError: If ``maf``, ``cfd_threshold`` or ``mit_threshold`` is not finite;
            if the scorer cannot serve the bulge budget; or if a region names a contig
            the reference does not have.
    """
    # Materialize a one-shot patient iterable. `search` reads it twice — once to count
    # how much of it covers the searched region, once to enumerate the personalized
    # sites — and the parameter is typed `Iterable`, so a generator lost the *second*
    # pass: the pass that actually personalizes the search. The failure is silent and
    # inverted, because the count from the first pass then reports that patient data
    # was used while none of it was. Haplotypes were already materialized this way;
    # this is the sibling that was not.
    #
    # Copied unconditionally. An `isinstance(..., Sequence)` pass-through was the first
    # version, justified by preserving the attribute `_PatientVariants` carries — but
    # the caller keeps its own object either way, so that justification was empty, and
    # the mutation run showed nothing could tell the two apart. On cost it does not earn
    # its keep either: 470 copies of a 10,000-variant list is 10 ms in total. One branch
    # is worth more than a saved microsecond.
    if patient_vcf is not None:
        patient_vcf = list(patient_vcf)
    # Refuse a non-finite fraction before anything is scanned. Click's `min=0.0,
    # max=1.0` rejects -1, 2 and inf and accepts NaN, and each of these three then
    # reaches a comparison that NaN makes False -- silently reporting every site, or
    # none. See `_bounds` for which way each one failed.
    reject_non_finite(maf=maf, cfd_threshold=cfd_threshold, mit_threshold=mit_threshold)
    sp = _spacer_str(spacer)
    # An ambiguous spacer position cannot be scored. The CFD matrix has no entry for
    # it, so the aligner treats it as a mismatch and the site scores toward 0 — which
    # is the *optimistic* direction on a safety axis: the true base is unknown and
    # might match perfectly. A degenerate spacer is a legitimate reagent (the oligo
    # layer says so explicitly), so this is recorded rather than refused, but it must
    # not read as "this guide is clean".
    ambiguous_spacer_positions = tuple(
        i + 1 for i, base in enumerate(sp.upper()) if base not in "ACGT"
    )
    primary = scorer if scorer is not None else CfdScorer()
    # Refuse a bulge budget the aligner cannot search, before a genome is touched.
    # `scan_sequence` refuses too, but only once a region is in hand: a whole-genome
    # run would spend its setup before saying the budget was never searchable.
    check_bulge_budget(dna_bulges, rna_bulges)
    # Refuse a scorer/budget combination the scorer cannot serve, before scanning
    # anything. The MIT score is defined only for an ungapped 20-nt alignment, so a
    # bulge budget makes it raise partway through the scan with a message about the
    # *alignment* length — which reads as a complaint about the caller's spacer, and
    # the caller's spacer is fine. This lived in the CLI, so the library, the cohort
    # and any future web caller still hit the deep failure; it belongs here, where
    # every caller passes.
    if primary.method is ScoreMethod.MIT and (dna_bulges or rna_bulges):
        # Both spellings, because this check was deliberately moved out of the CLI so
        # every caller would hit it — and `dna_bulges=0` is a Python keyword argument,
        # which is not something `aforge offtarget --scorer mit` can be given. The
        # default bulge budget is non-zero, so this refusal is what a caller meets the
        # first time they choose this scorer; a remedy they have to translate is half a
        # remedy.
        raise ValueError(
            "the MIT score is undefined for bulged alignments; set both bulge budgets to "
            "zero (`--dna-bulges 0 --rna-bulges 0` on the command line, `dna_bulges=0, "
            "rna_bulges=0` from Python), or use the CFD scorer, which scores bulged hits"
        )
    scan_pam = low_stringency_pam(pam)
    search_regions = list(regions) if regions is not None else _contig_regions(reference)
    # Fail on a region this reference cannot serve, naming the offender. A panel built
    # against another assembly or naming convention is the ordinary way this happens,
    # and it used to surface as a bare `KeyError` from deep inside the fetch. The CLI
    # had this check and the library did not, so only one of three callers got an
    # answer they could act on — and skipping the region instead would be worse than
    # either, because a smaller search reports fewer off-targets, the direction that
    # reads as safer and is not.
    _reject_unknown_contigs(search_regions, reference)
    search_regions = _rename_to_reference(search_regions, reference)
    haplotype_list = list(haplotypes)

    # A genome_index built from a different assembly than `reference` would anchor
    # PAMs over the index's sequence while reading bases/coordinates from this
    # reference — silently wrong hits. Fail closed when both builds are known and
    # disagree (content-addressing guards the FM cache, but not this consumer seam).
    if genome_index is not None:
        if reference.build is not None and genome_index.build is not None:
            if not assembly_matches(genome_index.build, reference.build):
                raise ValueError(
                    f"genome_index was built for assembly {genome_index.build!r} but the "
                    f"reference is {reference.build!r}; a mismatched index yields silently "
                    "wrong coordinates"
                )
        # The label comparison above fails *open* whenever either side is unlabelled,
        # which is exactly the index nobody wrote the genome down for. Contig lengths
        # are recorded and cost nothing to compare, and they do not depend on a name.
        disagreement = genome_index.disagreement_with(reference)
        if disagreement is not None:
            raise ValueError(
                f"genome_index does not index this reference: {disagreement}; a mismatched "
                "index yields silently wrong coordinates"
            )
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
            on_target=on_target,
        )
        cached = cache.get(signature)
        if cached is not None:
            return cached

    tagged: list[tuple[Hit, SiteProvenance]] = []
    ref_prov = SiteProvenance(origin=SiteOrigin.REFERENCE)

    # Stage 1 — reference candidate search. The linear PAM pass is the default at
    # every size; the FM-index seed-and-extend is opt-in (see FM_INDEX_AUTO_ENGAGES).
    # How much of the requested sequence could actually be searched. A window holding
    # an assembly gap or an IUPAC ambiguity code is not scannable, and a scan over a
    # region that is mostly gap reports the same "0 sites" as one over fully-resolved
    # sequence — "we found nothing" and "we found nothing in the 1% of your region that
    # is sequenced" are different claims, and only one of them is safe to act on.
    # Counted with `str.count` (four C-level passes) rather than per base, so this adds
    # nothing meaningful to a scan that is already walking the same bytes.
    total_bases = 0
    resolved_bases = 0
    for region in search_regions:
        seq = str(reference.fetch(region.model_copy(update={"strand": Strand.PLUS})))
        total_bases += len(seq)
        resolved_bases += _resolved_base_count(seq)
        if genome_index is not None and _is_whole_contig(region, reference, genome_index):
            # Persistent memory-mapped path: reuse the prebuilt contig index
            # (built once, survives runs) rather than rebuilding it per call.
            region_hits = scan_sequence(
                region.chrom,
                seq,
                sp,
                scan_pam,
                offset=0,
                fm_plus=genome_index.plus(region.chrom),
                fm_minus=genome_index.minus(region.chrom),
                **kw,
            )
        else:
            fm = use_fm_index if use_fm_index is not None else FM_INDEX_AUTO_ENGAGES
            region_hits = scan_sequence(
                region.chrom, seq, sp, scan_pam, offset=region.start, use_fm_index=fm, **kw
            )
        for hit in region_hits:
            tagged.append((hit, ref_prov))

    # Stage 2 — population augmentation (gnomAD de-novo PAM / seed changes).
    #
    # Count what the supplied source actually contributed *here*. A frequency file is
    # easy to supply and easy to have cover the wrong thing — one chromosome's download,
    # a region subset, a filtered slice — and when it contributes nothing the report is
    # byte-identical to a reference-only scan, with an empty ancestry breakdown that
    # reads as "clean". The warning for a *missing* source has existed for a while; a
    # source that is present and inert produced no warning at all, and is the more
    # dangerous case because the user believes they did it right.
    # Three states, kept distinct: key absent (no source given), 0 (given and covered
    # nothing here), n (given and contributed n). Counted without an `or` default,
    # which would collapse the first two — the whole point is that they differ.
    # Requested ancestries with no data behind them. Asking for `sas` against a source
    # whose records carry only `afr` and `nfe` contributes nothing and is dropped
    # silently, while the provenance snapshot records `sas` among the populations
    # considered — the report asserts an ancestry was examined when nothing for it
    # exists.
    #
    # This deliberately also covers the case where *no* ancestry source was supplied,
    # which it used to exclude with a trailing `if backed else ()` on the reasoning that
    # the CLI warns about it separately. It does -- to the terminal. The report a
    # collaborator is handed carried nothing, and a library or web caller was told
    # nothing at all: three ancestries requested, an empty breakdown, and no statement
    # anywhere in the artifact that the request went unhonored. The two cases differ in
    # how a user fixes them, not in what the report has to say, and "requested but not
    # examined" is true of both.
    backed: set[str] = set()
    if gnomad is not None:
        backed |= gnomad.available_populations
    for hap in haplotype_list:
        backed |= {pop for pop, freq in hap.frequencies.items() if freq > 0.0}
    unbacked = tuple(sorted(p for p in (populations or ()) if p not in backed))

    sources_considered: dict[str, int] = {}
    # Records skipped because they assert a reference base this genome does not have.
    # `sources_considered` counts records *found in the region*, which a whole file for
    # the wrong build satisfies, so the "supplied but contributing nothing" note could
    # not fire for the one case where it matters most.
    build_mismatch: dict[str, int] = {}
    if gnomad is not None:
        sources_considered["gnomad"] = 0
        gnomad_counts = SourceCounts()
        for region in search_regions:
            variants = gnomad.frequencies(region, populations=populations, maf=maf)
            sources_considered["gnomad"] += len(variants)
            tagged.extend(
                enumerate_population_sites(
                    sp,
                    scan_pam,
                    reference=reference,
                    variants=variants,
                    populations=populations,
                    maf=maf,
                    scorer=primary,
                    counts=gnomad_counts,
                    **kw,
                )
            )
        if gnomad_counts.build_mismatch:
            build_mismatch["gnomad"] = gnomad_counts.build_mismatch

    # Stage 3 — haplotype-aware evaluation.
    #
    # Haplotype panels and patient VCFs are consumed whole and region-filtered after
    # the fact, so "did this source cover the search?" is asked here against the same
    # regions. Same three states as gnomAD above: a panel supplied for another locus
    # yields 0 and must not read like a panel that had nothing to say.
    if haplotype_list or patient_vcf is not None:
        # Index the regions by canonical contig once. The obvious nested-any version
        # re-derives `canonical_contig` for every (entry, region) pair, which on a
        # 2,000-haplotype panel cost ~19% of a whole search — and `search()` runs once
        # per candidate, so a 470-candidate menu paid ~25 s for a label.
        spans: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for region in search_regions:
            spans[canonical_contig(region.chrom)].append((region.start, region.end))

        def _covered(chrom: str, pos: int) -> bool:
            return any(lo <= pos < hi for lo, hi in spans.get(canonical_contig(chrom), ()))

        if haplotype_list:
            sources_considered["haplotypes"] = sum(
                1 for hap in haplotype_list if any(_covered(v.chrom, v.pos) for v in hap.variants)
            )
        if patient_vcf is not None:
            sources_considered["patient-vcf"] = sum(
                1 for v in patient_vcf if _covered(v.chrom, v.pos)
            )
    haplotype_counts = SourceCounts()
    tagged.extend(
        enumerate_haplotype_sites(
            sp,
            scan_pam,
            reference=reference,
            haplotypes=haplotype_list,
            populations=populations,
            min_freq=maf,
            scorer=primary,
            counts=haplotype_counts,
            **kw,
        )
    )
    if haplotype_counts.build_mismatch:
        build_mismatch["haplotypes"] = haplotype_counts.build_mismatch

    # Stage 4 — optional patient-VCF personalization.
    if patient_vcf is not None:
        # The same accounting as gnomAD above. `_load_patient_variants` already refuses a
        # wrong-build VCF at load — but only on the CLI path, and only for variants it
        # resolves; a caller handing `design()` a list of `Variant` reaches here directly.
        patient_counts = SourceCounts()
        tagged.extend(
            enumerate_patient_sites(
                sp,
                scan_pam,
                reference=reference,
                variants=patient_vcf,
                scorer=primary,
                counts=patient_counts,
                **kw,
            )
        )
        if patient_counts.build_mismatch:
            build_mismatch["patient-vcf"] = patient_counts.build_mismatch

    # Honor an explicit `regions` scope across *every* pass. The reference and
    # population passes iterate `search_regions` and so are already in-scope, but the
    # haplotype and patient passes consume whole (possibly chromosome-wide) panels
    # with no region argument — without this filter a caller who scoped the search
    # would still see out-of-region hits those panels create. When `regions` is None
    # the scope is every contig, so this is a no-op.
    if regions is not None:
        tagged = [(hit, prov) for hit, prov in tagged if _in_regions(hit, search_regions)]

    # Stage 5 — score, threshold, de-duplicate, sort. Sites below the reporting
    # threshold are not reported, but their best per-placement score is carried into
    # the genome-wide aggregate (the sub-threshold tail) so a guide with a large
    # near-threshold tail cannot report the same specificity as a clean one.
    best: dict[tuple[str, int, int, Strand], OffTargetSite] = {}
    subthreshold: dict[tuple[str, int, int, Strand], float] = {}
    on_target_excluded: set[tuple[str, int, int, Strand]] = set()
    for hit, prov in tagged:
        if _is_on_target(hit, on_target):
            # The guide's own protospacer: the intended target, not an off-target.
            # Excluded from both the reported sites and the sub-threshold tail — and
            # counted, because an exclusion that removed forty placements reports the
            # same "0 sites, specificity 1.000" as a guide that had none.
            on_target_excluded.add((hit.chrom, hit.start, hit.end, hit.strand))
            continue
        cfd, mit = _scores(hit, primary)
        key = (hit.chrom, hit.start, hit.end, hit.strand)
        if cfd < cfd_threshold and (mit if mit is not None else 0.0) < mit_threshold:
            subthreshold[key] = max(subthreshold.get(key, 0.0), cfd)
            continue
        site = _to_site(hit, prov, cfd, primary.method, mit, _site_matrix(hit, primary))
        existing = best.get(key)
        if existing is None or site.score > existing.score:
            best[key] = site

    # A placement that ultimately cleared the threshold is a reported site, not tail.
    suppressed = {key: score for key, score in subthreshold.items() if key not in best}
    subthreshold_sum = sum(suppressed.values())
    sites = tuple(sorted(best.values(), key=lambda s: s.score, reverse=True))
    report = OffTargetReport(
        spacer=sp,
        pam=pam.pattern,
        sites=sites,
        mismatch_threshold=mismatches,
        dna_bulge_budget=dna_bulges,
        rna_bulge_budget=rna_bulges,
        cfd_threshold=cfd_threshold,
        mit_threshold=mit_threshold,
        searched_bases=total_bases,
        resolved_bases=resolved_bases,
        sources_considered=sources_considered,
        source_build_mismatch=build_mismatch,
        ambiguous_spacer_positions=ambiguous_spacer_positions,
        scanned_pam=scan_pam.pattern,
        unbacked_populations=unbacked,
        available_populations=tuple(sorted(backed)),
        # Only when an ancestry source was actually supplied: on a reference-only
        # scan the cut-off never applied, and printing it would describe a filter
        # that did nothing.
        maf_threshold=maf if (gnomad is not None or haplotype_list) else None,
        reference_build=reference.build or "hg38",
        scorer=primary.name,
        score_matrix=getattr(primary, "matrix", None),
        subthreshold_score_sum=subthreshold_sum,
        subthreshold_placements=len(suppressed),
        on_target_excluded_placements=len(on_target_excluded),
    )
    if cache is not None and signature is not None:
        cache.put(signature, report)
    return report
