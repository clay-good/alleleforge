"""The SpCas9 design vertical: variant to ranked DesignCandidates.

:func:`design_cas9` realizes the full nuclease slice the spec calls for —
**enumerate -> efficiency -> outcome -> off-target -> candidate** — assembling one
:class:`~alleleforge.types.candidate.DesignCandidate` per actionable guide, each
carrying a calibrated efficiency interval, a predicted indel spectrum, and an
ancestry-stratified off-target report. The Phase 10 designer routes to this and
the other chemistries and ranks across them; here a transparent efficiency-then-
safety sort orders the nuclease candidates.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol

from alleleforge.data.gnomad import GnomadDB
from alleleforge.data.haplotypes import Haplotype
from alleleforge.enumerate.cas9 import NGG_PAM, enumerate_cas9, guide_context
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search as offtarget_search
from alleleforge.scoring.base import ensure_prediction
from alleleforge.scoring.cas9_efficiency import EnsembleEfficiencyScorer
from alleleforge.scoring.cas9_outcome import MicrohomologyOutcomePredictor
from alleleforge.types.candidate import DesignCandidate
from alleleforge.types.edit import Chemistry, EditIntent, EditOutcome
from alleleforge.types.guide import PAM, Guide
from alleleforge.types.offtarget import OffTargetReport
from alleleforge.types.prediction import Prediction
from alleleforge.types.provenance import ModelCheckpoint
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.types.variant import Variant
from alleleforge.variant.resolver import ResolvedVariant

#: Local sequence half-width (bp) used for outcome prediction around the cut.
_OUTCOME_FLANK = 20


class Cas9EfficiencyScorer(Protocol):
    """Structural type a Cas9 efficiency scorer must satisfy (see scoring)."""

    name: str

    def score(self, context: str) -> Prediction[float]:
        """Return a calibrated efficiency prediction."""
        ...


class Cas9OutcomePredictor(Protocol):
    """Structural type a Cas9 outcome predictor must satisfy (see scoring)."""

    def predict(self, context: str, cut: int, *, mark_frameshift: bool = False) -> EditOutcome:
        """Return the predicted indel spectrum at ``cut``."""
        ...


def _cut_outcome(
    guide: Guide, reference: ReferenceGenome, predictor: Cas9OutcomePredictor, mark_fs: bool
) -> EditOutcome:
    """Predict the indel spectrum at a guide's cut from local genomic context."""
    start = max(0, guide.cut_site - _OUTCOME_FLANK)
    end = guide.cut_site + _OUTCOME_FLANK
    context = str(
        reference.fetch(
            GenomicInterval(chrom=guide.placement.chrom, start=start, end=end, strand=Strand.PLUS)
        )
    )
    return predictor.predict(context, guide.cut_site - start, mark_frameshift=mark_fs)


def _flags(
    guide: Guide, efficiency: Prediction[float], offreport: OffTargetReport | None
) -> tuple[str, ...]:
    """Return free-form annotations for a candidate."""
    flags: list[str] = []
    if guide.pam.pattern != "NGG":
        flags.append(f"relaxed-pam:{guide.pam.pattern}")
    if not efficiency.in_distribution:
        flags.append("ood")
    if offreport is not None and offreport.population_sites:
        flags.append("population-offtarget")
    return tuple(flags)


def cas9_model_checkpoints() -> tuple[ModelCheckpoint, ...]:
    """Return the provenance checkpoints for the default Cas9 scorers.

    The default efficiency ensemble (``cas9-efficiency-ensemble``) and outcome
    predictor (``indelphi``) carry model cards; their card-derived
    :class:`ModelCheckpoint`s are stamped into a menu's provenance whenever the
    nuclease vertical runs.
    """
    return (
        EnsembleEfficiencyScorer().model_card().to_checkpoint(),
        MicrohomologyOutcomePredictor().model_card().to_checkpoint(),
    )


def design_cas9(
    resolved: ResolvedVariant,
    intent: EditIntent,
    *,
    reference: ReferenceGenome,
    efficiency_scorer: Cas9EfficiencyScorer | None = None,
    outcome_predictor: Cas9OutcomePredictor | None = None,
    pam: PAM = NGG_PAM,
    allow_ng: bool = False,
    allow_spry: bool = False,
    gnomad: GnomadDB | None = None,
    haplotypes: Iterable[Haplotype] = (),
    patient_vcf: Iterable[Variant] | None = None,
    populations: Sequence[str] | None = None,
    offtarget_regions: Sequence[GenomicInterval] | None = None,
    run_offtarget: bool = True,
    max_candidates: int | None = None,
) -> list[DesignCandidate]:
    """Design SpCas9 nuclease candidates for a resolved variant.

    Args:
        resolved: The resolved variant.
        intent: What the edit must accomplish (frameshift outcomes are marked
            intended for a knock-out).
        reference: The reference genome.
        efficiency_scorer: On-target efficiency scorer (default: the deep
            ensemble on a stub embedder).
        outcome_predictor: Indel-outcome predictor (default: the microhomology
            baseline).
        pam: Primary PAM (default ``NGG``).
        allow_ng: Allow ``NG`` guides if no ``NGG`` guide is actionable.
        allow_spry: Allow ``NRN``/``NYN`` guides if still none.
        gnomad: gnomAD DB for population-aware off-target (optional).
        haplotypes: Common haplotypes for haplotype-aware off-target (optional).
        patient_vcf: Personal variants for off-target personalization (optional).
        populations: Ancestry labels to query/stratify.
        offtarget_regions: Restrict the off-target search (default: every contig).
        run_offtarget: Run the off-target engine (set ``False`` to skip it).
        max_candidates: Cap the number of returned candidates.

    Returns:
        Candidates ordered by descending efficiency then ascending worst-case
        off-target score (best, safest first).
    """
    guides = enumerate_cas9(
        resolved, intent, reference=reference, pam=pam, allow_ng=allow_ng, allow_spry=allow_spry
    )
    scorer: Cas9EfficiencyScorer = efficiency_scorer or EnsembleEfficiencyScorer()
    predictor: Cas9OutcomePredictor = outcome_predictor or MicrohomologyOutcomePredictor()
    mark_fs = intent is EditIntent.KNOCK_OUT

    # A scorer may declare the asymmetric window it reads (e.g. the trained Rule
    # Set 3 model's 30-mer); otherwise the symmetric default applies.
    flank: tuple[int, int] | None = getattr(scorer, "context_flank", None)
    ctx_kwargs = {"flank_5": flank[0], "flank_3": flank[1]} if flank is not None else {}

    candidates: list[DesignCandidate] = []
    for guide in guides:
        efficiency = ensure_prediction(
            scorer.score(guide_context(guide, reference, **ctx_kwargs)), who=scorer.name
        )
        outcome = _cut_outcome(guide, reference, predictor, mark_fs)
        offreport: OffTargetReport | None = None
        if run_offtarget:
            offreport = offtarget_search(
                guide.spacer,
                pam,
                reference=reference,
                gnomad=gnomad,
                haplotypes=haplotypes,
                patient_vcf=patient_vcf,
                populations=populations,
                regions=offtarget_regions,
            )
        candidates.append(
            DesignCandidate(
                chemistry=Chemistry.CAS9_NUCLEASE,
                guide=guide,
                efficiency=efficiency,
                outcome=outcome,
                offtarget=offreport,
                flags=_flags(guide, efficiency, offreport),
                rationale=(
                    f"{guide.pam.pattern} guide on {guide.placement.strand.value} strand, "
                    f"cut {guide.cut_site}; efficiency {efficiency.value:.2f}"
                ),
            )
        )
    candidates.sort(key=_candidate_sort_key, reverse=False)
    return candidates[:max_candidates] if max_candidates is not None else candidates


def _candidate_sort_key(candidate: DesignCandidate) -> tuple[float, float]:
    """Sort key: higher efficiency first, then lower worst-case off-target."""
    eff = candidate.efficiency.value if candidate.efficiency is not None else 0.0
    worst = candidate.offtarget.worst_score() if candidate.offtarget is not None else 0.0
    return (-eff, worst)
