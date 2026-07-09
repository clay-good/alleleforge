"""The prime-editing design vertical: variant to ranked pegRNA candidates.

:func:`design_prime` realizes the flagship slice — **enumerate -> efficiency ->
outcome -> off-target -> candidate** — assembling one
:class:`~alleleforge.types.candidate.DesignCandidate` per pegRNA, each carrying a
calibrated efficiency interval (with prominent OOD honesty), an
intended-vs-byproduct distribution, and an ancestry-stratified off-target report
computed over **both** nicks (the pegRNA nick and the ngRNA nick), merged into one
report. This is the chemistry where AlleleForge contributes the most: it unifies
the four axes no single open-source tool combines today.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol

from alleleforge.data.gnomad import GnomadDB
from alleleforge.data.haplotypes import Haplotype
from alleleforge.enumerate.prime import NGG_PAM, enumerate_prime
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search as offtarget_search
from alleleforge.scoring.base import ensure_prediction
from alleleforge.scoring.prime_efficiency import PridictScorer
from alleleforge.scoring.prime_outcome import PrimeOutcomePredictor
from alleleforge.types.candidate import DesignCandidate
from alleleforge.types.edit import Chemistry, EditIntent
from alleleforge.types.guide import PAM, PegRNA, Spacer
from alleleforge.types.offtarget import OffTargetReport, OffTargetSite
from alleleforge.types.prediction import Prediction
from alleleforge.types.provenance import ModelCheckpoint
from alleleforge.types.sequence import GenomicInterval
from alleleforge.types.variant import Variant
from alleleforge.variant.resolver import ResolvedVariant


class PrimeEfficiencyScorer(Protocol):
    """Structural type a prime-efficiency scorer must satisfy."""

    name: str

    def score(self, pegrna: PegRNA, *, cell_context: str | None = None) -> Prediction[float]:
        """Return a calibrated efficiency prediction for a pegRNA."""
        ...


def _merge_offtarget(peg: OffTargetReport, ngrna: OffTargetReport | None) -> OffTargetReport:
    """Merge the pegRNA-nick and ngRNA-nick reports into one (dedup by locus)."""
    if ngrna is None:
        return peg
    best: dict[tuple[str, int, int, str], OffTargetSite] = {}
    for site in (*peg.sites, *ngrna.sites):
        key = (site.locus.chrom, site.locus.start, site.locus.end, site.locus.strand.value)
        if key not in best or site.score > best[key].score:
            best[key] = site
    sites = tuple(sorted(best.values(), key=lambda s: s.score, reverse=True))
    # Carry the scorer/matrix identity and the sub-threshold tail through the merge.
    # Both nick reports come from the same off-target search (same scorer), so peg's
    # `scorer`/`score_matrix` are the honest labels for the merged sites — without
    # them the report renders no "scoring basis" line for every PE3/PE3b candidate
    # (defeating the guarantee that the scorer/matrix are always named). The two
    # sub-threshold tails are summed so `specificity_score` still aggregates over the
    # near-threshold hits of *both* nicks rather than silently resetting to 0.0 (a
    # locus sub-threshold in one nick but reported in the other is counted in both,
    # which only lowers specificity — the conservative direction).
    return OffTargetReport(
        spacer=peg.spacer,
        pam=peg.pam,
        sites=sites,
        mismatch_threshold=peg.mismatch_threshold,
        reference_build=peg.reference_build,
        scorer=peg.scorer,
        score_matrix=peg.score_matrix,
        subthreshold_score_sum=peg.subthreshold_score_sum + ngrna.subthreshold_score_sum,
    )


#: Spacer GC band (Pol III): outside it, U6 transcription and synthesis suffer, so
#: the spacer is annotated (not dropped) as an inspectable quality caveat.
_GC_BAND = (0.30, 0.80)


def _flags(pegrna: PegRNA, efficiency: Prediction[float], run_offtarget: bool) -> tuple[str, ...]:
    """Return free-form annotations for a prime candidate."""
    flags: list[str] = []
    if pegrna.is_epegrna:
        flags.append(f"epegRNA:{pegrna.three_prime_motif.value}")
    ng = pegrna.nicking_guide
    flags.append("pe3b" if (ng and ng.seed_disrupting) else "pe3" if ng else "no-nick")
    if ng is not None and run_offtarget:
        flags.append("both-nicks-searched")
    if not efficiency.in_distribution:
        flags.append("ood")
    # Pol III transcription caveats, surfaced as inspectable annotations rather than
    # silent absence: a spacer not starting with G needs a prepended U6-start G, and
    # an out-of-band GC content hurts transcription/synthesis.
    spacer = str(pegrna.spacer.sequence).upper()
    if spacer and not spacer.startswith("G"):
        flags.append("no-5prime-g")
    gc = sum(b in "GC" for b in spacer) / len(spacer) if spacer else 0.0
    if not _GC_BAND[0] <= gc <= _GC_BAND[1]:
        flags.append(f"gc-out-of-band:{gc:.2f}")
    return tuple(flags)


def prime_model_checkpoints() -> tuple[ModelCheckpoint, ...]:
    """Return the provenance checkpoints for the default prime scorers.

    The default efficiency scorer is PRIDICT2.0 (``pridict2``), which carries a
    model card. The default outcome predictor is a card-free heuristic, so it
    contributes no checkpoint.
    """
    return (PridictScorer().model_card().to_checkpoint(),)


def design_prime(
    resolved: ResolvedVariant,
    intent: EditIntent = EditIntent.CORRECT,
    *,
    reference: ReferenceGenome,
    efficiency_scorer: PrimeEfficiencyScorer | None = None,
    outcome_predictor: PrimeOutcomePredictor | None = None,
    cell_context: str | None = None,
    pam: PAM = NGG_PAM,
    gnomad: GnomadDB | None = None,
    haplotypes: Iterable[Haplotype] = (),
    patient_vcf: Iterable[Variant] | None = None,
    populations: Sequence[str] | None = None,
    offtarget_regions: Sequence[GenomicInterval] | None = None,
    run_offtarget: bool = True,
    max_candidates: int | None = None,
) -> list[DesignCandidate]:
    """Design prime-editing candidates for a resolved variant.

    Args:
        resolved: The resolved variant (single-position edit).
        intent: What the edit must accomplish (sets start/desired alleles).
        reference: The reference genome.
        efficiency_scorer: Prime-efficiency scorer (default: PRIDICT2.0 baseline).
        outcome_predictor: Outcome predictor (default: the byproduct baseline).
        cell_context: Target cell context; outside HEK293T/K562 flags every
            efficiency prediction out-of-distribution.
        pam: The pegRNA PAM (default ``NGG``).
        gnomad: gnomAD DB for population-aware off-target (optional).
        haplotypes: Common haplotypes for haplotype-aware off-target (optional).
        patient_vcf: Personal variants for off-target personalization (optional).
        populations: Ancestry labels to query/stratify.
        offtarget_regions: Restrict the off-target search (default: every contig).
        run_offtarget: Run the off-target engine on both nicks (default on).
        max_candidates: Cap the number of returned candidates.

    Returns:
        Candidates ranked by descending efficiency; each carries a merged,
        ancestry-stratified off-target report over both nicks.
    """
    pegrnas = enumerate_prime(resolved, intent, reference=reference, pam=pam)
    scorer: PrimeEfficiencyScorer = efficiency_scorer or PridictScorer()
    predictor = outcome_predictor or PrimeOutcomePredictor()
    cache: dict[tuple[str, str | None], OffTargetReport] = {}

    def _search(spacer: Spacer) -> OffTargetReport:
        return offtarget_search(
            spacer,
            pam,
            reference=reference,
            gnomad=gnomad,
            haplotypes=haplotypes,
            patient_vcf=patient_vcf,
            populations=populations,
            regions=offtarget_regions,
        )

    def offtarget_for(pegrna: PegRNA) -> OffTargetReport | None:
        if not run_offtarget:
            return None
        ng = pegrna.nicking_guide
        ng_spacer = str(ng.spacer.sequence) if ng is not None else None
        key = (str(pegrna.spacer.sequence), ng_spacer)
        if key not in cache:
            peg_report = _search(pegrna.spacer)
            ng_report = _search(ng.spacer) if ng is not None else None
            cache[key] = _merge_offtarget(peg_report, ng_report)
        return cache[key]

    scored: list[tuple[DesignCandidate, float]] = []
    for pegrna in pegrnas:
        efficiency = ensure_prediction(
            scorer.score(pegrna, cell_context=cell_context), who=scorer.name
        )
        outcome = predictor.predict(pegrna)
        candidate = DesignCandidate(
            chemistry=Chemistry.PRIME,
            pegrna=pegrna,
            efficiency=efficiency,
            outcome=outcome.outcome,
            offtarget=offtarget_for(pegrna),
            flags=_flags(pegrna, efficiency, run_offtarget),
            rationale=(
                f"pegRNA on {pegrna.placement.strand.value if pegrna.placement else '?'} strand, "
                f"PBS {len(pegrna.pbs)} / RTT {len(pegrna.rtt)} "
                f"(+{pegrna.rtt_homology_3prime} homology); "
                f"efficiency {efficiency.value:.2f}, intended P={outcome.p_intended.value:.2f}"
            ),
        )
        scored.append((candidate, efficiency.value))

    scored.sort(key=lambda cv: cv[1], reverse=True)
    candidates = [c for c, _ in scored]
    return candidates[:max_candidates] if max_candidates is not None else candidates
