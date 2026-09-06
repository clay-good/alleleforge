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

from collections.abc import Iterable, MutableMapping, Sequence
from typing import Protocol

from alleleforge.data.annotations import EncodeTracks
from alleleforge.data.gnomad import GnomadDB
from alleleforge.data.haplotypes import Haplotype
from alleleforge.design.offtarget_flags import offtarget_flags
from alleleforge.design.outcome_flags import outcome_flags
from alleleforge.design.spacer_quality import spacer_quality_flags
from alleleforge.enumerate.prime import NGG_PAM, enumerate_prime
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.model_zoo.registry import ModelCard
from alleleforge.offtarget.engine import search as offtarget_search
from alleleforge.scoring.base import ensure_prediction
from alleleforge.scoring.prime_efficiency import PridictScorer
from alleleforge.scoring.prime_outcome import PrimeOutcomePredictor
from alleleforge.types.candidate import DesignCandidate
from alleleforge.types.edit import Chemistry, EditIntent, EditOutcome
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

    def model_card(self) -> ModelCard:
        """Return the card whose checkpoint is stamped into provenance."""
        ...

    def score(
        self,
        pegrna: PegRNA,
        *,
        cell_context: str | None = None,
        chromatin: tuple[EncodeTracks, GenomicInterval, str] | None = None,
    ) -> Prediction[float]:
        """Return a calibrated efficiency prediction for a pegRNA.

        ``chromatin`` is an optional ``(tracks, interval, track_name)`` for an
        ePRIDICT-style open-chromatin adjustment; a scorer that does not model
        chromatin ignores it.
        """
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
    # Copy-and-update rather than rebuild field by field. Both nick reports come from
    # the same search over the same reference with the same scorer, so every remaining
    # field on `peg` — the scorer/matrix identity, the reference build, and each budget
    # and cut-off that narrowed the scan — is already the honest label for the merged
    # sites. Only the two that genuinely aggregate are named: the deduplicated sites,
    # and the summed sub-threshold tails so `specificity_score` still accounts for the
    # near-threshold hits of *both* nicks (a locus sub-threshold in one nick but
    # reported in the other is counted twice, which only lowers specificity — the
    # conservative direction).
    #
    # The field-by-field rebuild this replaces silently reset every field it forgot to
    # its default, and it forgot three times: the scorer/matrix identity, the
    # sub-threshold tail, and the bulge budgets and CFD/MIT cut-offs. `model_copy`
    # makes that class of omission impossible — a field added to `OffTargetReport`
    # tomorrow is carried through the merge without touching this function.
    return peg.model_copy(
        update={
            "sites": sites,
            "subthreshold_score_sum": peg.subthreshold_score_sum + ngrna.subthreshold_score_sum,
        }
    )


#: Below this nick-to-nick distance (nt) a PE3 candidate is annotated as
#: close-nicked. Two nicks on opposite strands close together are, in effect, a
#: staggered double-strand break — the outcome prime editing exists to avoid — and the
#: indel byproduct rate climbs as they approach. The PE3 nicking guides characterized
#: when the method was introduced sit at roughly 40-90 nt from the pegRNA nick; this
#: constant is a deliberately conservative floor well inside that, not a fitted
#: threshold, and it drives an inspectable annotation only. It does **not** enter
#: ranking: turning nick distance into a score would need a byproduct model calibrated
#: against real PE3 data, which AlleleForge does not have, and inventing a weight is
#: worse than showing the number and letting the user apply the literature.
CLOSE_NICK_NT = 30


def _flags(
    pegrna: PegRNA,
    efficiency: Prediction[float],
    offreport: OffTargetReport | None,
    outcome: EditOutcome | None,
    *,
    chromatin_adjusted: bool = False,
) -> tuple[str, ...]:
    """Return free-form annotations for a prime candidate.

    Every flag is attached here with ``flags.append``. That uniformity is load-bearing:
    the classification guard reads the append literals out of the source to check no
    flag is unclassified, and a flag attached some other way is invisible to it —
    twice now a novel construction slipped past exactly that check.
    """
    flags: list[str] = []
    # An unsearched safety axis scores 1.00 in the composite — the reassuring extreme
    # for something nobody measured. The ranking cannot fix that without inventing a
    # policy, so the candidate says plainly that the number is unearned.
    # Shared with the other two verticals: whether a search ran, whether any nominated
    # site is high-scoring, and whether population variation contributed. Prime was the
    # only chemistry never to flag a population off-target, which its siblings did.
    flags += offtarget_flags(offreport)
    flags += outcome_flags(outcome)
    if chromatin_adjusted:
        flags.append("chromatin-adjusted")
    if pegrna.is_epegrna:
        flags.append(f"epegRNA:{pegrna.three_prime_motif.value}")
    ng = pegrna.nicking_guide
    flags.append("pe3b" if (ng and ng.seed_disrupting) else "pe3" if ng else "no-nick")
    # The nick-to-nick distance is the PE3 design parameter, and it was computed,
    # stored, and then shown to nobody: two PE3 candidates were indistinguishable in
    # the menu on the one number the literature says to choose between them by.
    if ng is not None:
        flags.append(f"nick-distance:{ng.nick_offset:+d}nt")
        if abs(ng.nick_offset) < CLOSE_NICK_NT:
            flags.append("close-nick")
    # What the RT template actually writes. A menu that shows only geometry hides
    # whether a candidate installs a single base or a 29-nt insertion — the same
    # numbers, very different reagents at the bench.
    written = pegrna.templated_edit_length
    if written != 1:
        flags.append(f"templated-edit:{written}nt")
    if ng is not None and offreport is not None:
        flags.append("both-nicks-searched")
    if not efficiency.in_distribution:
        flags.append("ood")
    # Pol III transcription caveats. Shared with every other chemistry: they are
    # properties of the spacer as a transcribed reagent, not of prime editing.
    flags += spacer_quality_flags(str(pegrna.spacer.sequence))
    return tuple(flags)


def prime_model_checkpoints(
    efficiency_scorer: PrimeEfficiencyScorer | None = None,
    outcome_predictor: PrimeOutcomePredictor | None = None,
) -> tuple[ModelCheckpoint, ...]:
    """Return the provenance checkpoints for the prime scorers actually used.

    Both defaults are transparent heuristics and each carries its *own* card —
    ``pridict2-baseline`` and ``prime-outcome-baseline`` — rather than the trained
    ``pridict2`` card, so a default run's provenance never records trained-only
    training data or failure modes for numbers a heuristic produced. When an
    override is supplied, the override's card is recorded instead, so provenance
    names the model that scored the candidates rather than the default it replaced
    — matching the nuclease and base-editor verticals. No *trained* per-pegRNA
    prime scorer ships today (``PridictEngineAdapter`` is sequence-level; the
    cross-check adapters are refusing placeholders), so in practice the defaults
    are what a run records until that R1 gap closes.
    """
    efficiency = efficiency_scorer if efficiency_scorer is not None else PridictScorer()
    outcome = outcome_predictor if outcome_predictor is not None else PrimeOutcomePredictor()
    return (
        efficiency.model_card().to_checkpoint(),
        outcome.model_card().to_checkpoint(),
    )


#: What a cached off-target report depends on: both spacers *and* both placements.
#: The report is spacer-specific, but the on-target exclusion is *locus*-specific,
#: so two pegRNAs sharing a spacer pair at different loci must not share an entry.
_CacheKey = tuple[str, str | None, str | None, str | None]


def _offtarget_cache_key(pegrna: PegRNA) -> _CacheKey:
    """Return the key under which ``pegrna``'s merged off-target report is cached.

    A prime design routinely yields hundreds of pegRNAs over a handful of distinct
    spacers — every PBS x RTT-homology combination reuses one protospacer — so
    caching the scan is what keeps the vertical affordable. The key must therefore
    name every input the cached value depends on, and the placements are two of
    them: the report has each spacer's own locus excluded from it, and that
    exclusion is locus-specific. Keying on the spacers alone would let a pegRNA at
    one locus be handed a report that excluded a *different* locus — dropping a
    genuine paralogous off-target for it. No locus was found that actually
    produces a spacer-pair collision across placements (the enumerator's RT-reach
    window makes it hard to arrange), so this closes the key/value mismatch rather
    than a demonstrated miss.
    """
    ng = pegrna.nicking_guide
    return (
        str(pegrna.spacer.sequence),
        str(ng.spacer.sequence) if ng is not None else None,
        str(pegrna.placement) if pegrna.placement is not None else None,
        str(ng.placement) if ng is not None else None,
    )


def design_prime(
    resolved: ResolvedVariant,
    intent: EditIntent = EditIntent.CORRECT,
    *,
    reference: ReferenceGenome,
    efficiency_scorer: PrimeEfficiencyScorer | None = None,
    outcome_predictor: PrimeOutcomePredictor | None = None,
    cell_context: str | None = None,
    encode_tracks: EncodeTracks | None = None,
    chromatin_track: str | None = None,
    pam: PAM = NGG_PAM,
    gnomad: GnomadDB | None = None,
    haplotypes: Iterable[Haplotype] = (),
    patient_vcf: Iterable[Variant] | None = None,
    populations: Sequence[str] | None = None,
    offtarget_regions: Sequence[GenomicInterval] | None = None,
    run_offtarget: bool = True,
    max_candidates: int | None = None,
    tally: MutableMapping[str, int] | None = None,
) -> list[DesignCandidate]:
    """Design prime-editing candidates for a resolved variant.

    Args:
        resolved: The resolved variant (any precise small edit — substitution,
            MNV, insertion, deletion, or delins — within the RT template budgets).
        intent: What the edit must accomplish (sets start/desired alleles).
        reference: The reference genome.
        efficiency_scorer: Prime-efficiency scorer (default: PRIDICT2.0 baseline).
        outcome_predictor: Outcome predictor (default: the byproduct baseline).
        cell_context: Target cell context; outside HEK293T/K562 flags every
            efficiency prediction out-of-distribution.
        encode_tracks: Optional ENCODE accessibility tracks for an ePRIDICT-style
            open-chromatin efficiency adjustment. Opt-in: with no tracks the
            efficiency is the pure pegRNA-geometry baseline (unchanged default).
        chromatin_track: The track name to read from ``encode_tracks`` (required to
            enable the adjustment). An unknown track name fails closed (raises).
        pam: The pegRNA PAM (default ``NGG``).
        gnomad: gnomAD DB for population-aware off-target (optional).
        haplotypes: Common haplotypes for haplotype-aware off-target (optional).
        patient_vcf: Personal variants for off-target personalization (optional).
        populations: Ancestry labels to query/stratify.
        offtarget_regions: Restrict the off-target search (default: every contig).
        run_offtarget: Run the off-target engine on both nicks (default on).
        max_candidates: Cap the number of returned candidates.
        tally: Optional mapping that records why each protospacer was rejected, so a
            caller can explain an empty result rather than only report it.

    Returns:
        Candidates ranked by descending efficiency; each carries a merged,
        ancestry-stratified off-target report over both nicks.
    """
    pegrnas = enumerate_prime(resolved, intent, reference=reference, pam=pam, tally=tally)
    scorer: PrimeEfficiencyScorer = efficiency_scorer or PridictScorer()
    predictor = outcome_predictor or PrimeOutcomePredictor()
    cache: dict[_CacheKey, OffTargetReport] = {}

    def _search(spacer: Spacer, on_target: GenomicInterval | None) -> OffTargetReport:
        return offtarget_search(
            spacer,
            pam,
            reference=reference,
            gnomad=gnomad,
            haplotypes=haplotypes,
            patient_vcf=patient_vcf,
            populations=populations,
            regions=offtarget_regions,
            on_target=on_target,
        )

    def offtarget_for(pegrna: PegRNA) -> OffTargetReport | None:
        if not run_offtarget:
            return None
        ng = pegrna.nicking_guide
        key = _offtarget_cache_key(pegrna)
        if key not in cache:
            # Each spacer's own protospacer is its intended nick, not an off-target,
            # so exclude each from its own report before the two-nick merge.
            peg_report = _search(pegrna.spacer, pegrna.placement)
            ng_report = _search(ng.spacer, ng.placement) if ng is not None else None
            cache[key] = _merge_offtarget(peg_report, ng_report)
        return cache[key]

    # Opt-in ePRIDICT open-chromatin adjustment: enabled only when both a tracks
    # source and a track name are supplied. `EncodeTracks.signal` raises on an
    # unknown track, so a mis-named track fails closed rather than silently
    # producing an unadjusted efficiency labeled chromatin-aware.
    chromatin_enabled = encode_tracks is not None and chromatin_track is not None

    # How many candidates the track actually moved. A track can be supplied, recorded
    # in provenance, and cover none of the loci — in which case every efficiency is the
    # unadjusted one while the run looks chromatin-aware. Same shape as a population
    # source that covers nothing: present, recorded, and inert.
    adjusted_by_chromatin = 0
    scored: list[tuple[DesignCandidate, float]] = []
    for pegrna in pegrnas:
        chromatin: tuple[EncodeTracks, GenomicInterval, str] | None = None
        chromatin_note = ""
        if chromatin_enabled and pegrna.placement is not None:
            assert encode_tracks is not None and chromatin_track is not None
            signal = encode_tracks.signal(chromatin_track, pegrna.placement)
            chromatin = (encode_tracks, pegrna.placement, chromatin_track)
            # An uncovered locus (signal 0) is a no-op in the scorer, so only note an
            # adjustment that actually moved the estimate — never claim chromatin
            # evidence where the track had none.
            if signal > 0.0:
                chromatin_note = f"; chromatin-adjusted (accessibility {signal:.2f})"
                adjusted_by_chromatin += 1
        efficiency = ensure_prediction(
            scorer.score(pegrna, cell_context=cell_context, chromatin=chromatin),
            who=scorer.name,
        )
        outcome = predictor.predict(pegrna)
        # Bound once: the flags and the candidate must describe the same report, and
        # `_flags` previously received only a boolean — which is why prime was the one
        # chemistry that never flagged a population off-target. The information had
        # never reached the flag builder.
        peg_offtarget = offtarget_for(pegrna)
        candidate = DesignCandidate(
            chemistry=Chemistry.PRIME,
            pegrna=pegrna,
            efficiency=efficiency,
            outcome=outcome.outcome,
            # The scorer returns `p_intended` as a Prediction; passing only
            # `outcome.outcome` dropped it, and every surface then recomputed a
            # bare sum over the alleles.
            p_intended=outcome.p_intended,
            offtarget=peg_offtarget,
            flags=_flags(
                pegrna,
                efficiency,
                peg_offtarget,
                outcome.outcome,
                chromatin_adjusted=bool(chromatin_note),
            ),
            rationale=(
                f"pegRNA on {pegrna.placement.strand.value if pegrna.placement else '?'} strand, "
                f"PBS {len(pegrna.pbs)} / RTT {len(pegrna.rtt)} "
                f"({pegrna.templated_edit_length} nt written, "
                f"+{pegrna.rtt_homology_3prime} homology); "
                f"efficiency {efficiency.value:.2f}, intended P={outcome.p_intended.value:.2f}"
                f"{chromatin_note}"
            ),
        )
        scored.append((candidate, efficiency.value))

    scored.sort(key=lambda cv: cv[1], reverse=True)
    candidates = [c for c, _ in scored]
    return candidates[:max_candidates] if max_candidates is not None else candidates
