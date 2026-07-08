"""Assemble a ranked menu into a structured, serializable report model.

[`build_report`][alleleforge.report.builder.build_report] flattens a
:class:`~alleleforge.types.candidate.RankedMenu` into a :class:`DesignReport`: a
self-contained, JSON-serializable document with the research-use disclaimer
first and full provenance last, and in between one :class:`CandidateReport` per
candidate carrying its reagent summary, calibrated efficiency, top outcome
alleles, an **ancestry-stratified** off-target table, cloning oligos, flags, and
ranking rationale. Renderers (JSON/TSV, HTML, PDF) consume this model and add no
business logic of their own.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from alleleforge.report.oligos import (
    PegRNAOligos,
    SgRnaOligos,
    VectorScheme,
    oligos_for,
)
from alleleforge.types.candidate import DesignCandidate, RankedMenu
from alleleforge.types.edit import AlleleOutcome, Chemistry
from alleleforge.types.prediction import Prediction
from alleleforge.types.provenance import Provenance

#: The research-use disclaimer that leads every rendered report.
RESEARCH_USE_DISCLAIMER = (
    "AlleleForge is a research tool. It is not a medical device and does not "
    "provide medical advice. The candidates below are ranked, explicitly "
    "uncertain computational hypotheses. Every off-target nomination is "
    "computational and must be experimentally validated (e.g. GUIDE-seq / "
    "CHANGE-seq / amplicon sequencing) before any wet-lab or therapeutic use."
)


class AncestryOffTarget(BaseModel):
    """The worst-case off-target score for one ancestry."""

    model_config = ConfigDict(frozen=True)

    ancestry: str
    worst_score: float


def _reagent_summary(candidate: DesignCandidate) -> str:
    """Return a one-line human description of the candidate's reagent."""
    if candidate.guide is not None:
        g = candidate.guide
        return (
            f"SpCas9 sgRNA {g.spacer.sequence} "
            f"({g.pam.pattern} PAM, {g.placement.strand.value} strand, cut {g.cut_site})"
        )
    if candidate.base_edit_window is not None:
        w = candidate.base_edit_window
        return f"{w.editor} sgRNA {w.spacer.sequence} (window {w.window[0]}-{w.window[1]})"
    if candidate.pegrna is not None:
        p = candidate.pegrna
        nick = (
            "PE3b"
            if (p.nicking_guide and p.nicking_guide.seed_disrupting)
            else ("PE3" if p.nicking_guide else "PE2")
        )
        return (
            f"pegRNA spacer {p.spacer.sequence}; PBS {len(p.pbs)} nt / RTT {len(p.rtt)} nt; "
            f"{p.three_prime_motif.value} motif; {nick}"
        )
    return "no reagent"


class CandidateReport(BaseModel):
    """One candidate, flattened for presentation and export.

    Attributes:
        rank: 1-based rank within the menu.
        chemistry: The candidate's chemistry.
        on_pareto_front: Whether the candidate is Pareto-optimal.
        reagent: A one-line human description of the reagent.
        efficiency: The calibrated efficiency prediction, if scored.
        bystander_burden: Calibrated expected bystander-edit count, for
            base-editor candidates (``None`` otherwise).
        p_intended: Summed probability of the intended allele(s), if scored.
        outcome_top: The highest-probability outcome alleles (descending).
        n_offtarget_sites: Number of nominated off-target sites, if searched.
        offtarget_specificity: Aggregate genome-wide specificity in ``(0, 1]``
            (Hsu-2013-style ``1/(1+Σ scores)``), if searched; ``1.0`` = no off-targets.
        offtarget_by_ancestry: Worst-case off-target score per ancestry.
        oligos: Cloning-ready oligos for the reagent, if requested.
        oligos_requested: Whether oligos were requested for this report. Lets a
            render distinguish a **reagent-free** candidate (requested, but nothing
            to synthesize) from one where oligos were simply not asked for, so a
            reagent-free candidate can say so rather than omitting the section.
        flags: Free-form candidate flags.
        rationale: The candidate's ranking rationale.
    """

    model_config = ConfigDict(frozen=True)

    rank: int
    chemistry: Chemistry
    on_pareto_front: bool
    reagent: str
    efficiency: Prediction[float] | None
    bystander_burden: Prediction[float] | None
    p_intended: float | None
    outcome_top: tuple[AlleleOutcome, ...]
    n_offtarget_sites: int | None
    offtarget_specificity: float | None
    offtarget_by_ancestry: tuple[AncestryOffTarget, ...]
    oligos: SgRnaOligos | PegRNAOligos | None
    oligos_requested: bool = False
    flags: tuple[str, ...]
    rationale: str | None


class DesignReport(BaseModel):
    """A complete, serializable design report.

    Attributes:
        title: Report title.
        disclaimer: The research-use disclaimer (leads every render).
        variant: The target variant string, if supplied.
        intent: The edit intent, if known.
        weights: The ranking weights used.
        candidates: One :class:`CandidateReport` per menu candidate, in rank order.
        provenance: The menu's provenance block (ends every render).
    """

    model_config = ConfigDict(frozen=True)

    title: str
    disclaimer: str
    variant: str | None
    intent: str | None
    weights: dict[str, float]
    candidates: tuple[CandidateReport, ...]
    provenance: Provenance | None

    @property
    def best(self) -> CandidateReport | None:
        """Return the top-ranked candidate report, if any."""
        return self.candidates[0] if self.candidates else None


def _candidate_report(
    candidate: DesignCandidate,
    *,
    rank: int,
    on_pareto_front: bool,
    top_alleles: int,
    with_oligos: bool,
    scheme: VectorScheme | None,
) -> CandidateReport:
    """Flatten one candidate into a :class:`CandidateReport`."""
    outcome_top: tuple[AlleleOutcome, ...] = ()
    p_intended: float | None = None
    if candidate.outcome is not None:
        ordered = sorted(candidate.outcome.alleles, key=lambda a: a.probability, reverse=True)
        outcome_top = tuple(ordered[:top_alleles])
        p_intended = candidate.outcome.p_intended

    n_sites: int | None = None
    specificity: float | None = None
    ancestry_rows: tuple[AncestryOffTarget, ...] = ()
    if candidate.offtarget is not None:
        n_sites = candidate.offtarget.n_sites
        specificity = candidate.offtarget.specificity_score()
        strata = candidate.offtarget.ancestry_stratification()
        ancestry_rows = tuple(
            AncestryOffTarget(ancestry=a, worst_score=s)
            for a, s in sorted(strata.items(), key=lambda kv: kv[1], reverse=True)
        )

    oligos = oligos_for(candidate, scheme=scheme) if with_oligos else None
    return CandidateReport(
        rank=rank,
        chemistry=candidate.chemistry,
        on_pareto_front=on_pareto_front,
        reagent=_reagent_summary(candidate),
        efficiency=candidate.efficiency,
        bystander_burden=candidate.bystander_burden,
        p_intended=p_intended,
        outcome_top=outcome_top,
        n_offtarget_sites=n_sites,
        offtarget_specificity=specificity,
        offtarget_by_ancestry=ancestry_rows,
        oligos=oligos,
        oligos_requested=with_oligos,
        flags=candidate.flags,
        rationale=candidate.rationale,
    )


def build_report(
    menu: RankedMenu,
    *,
    variant: str | None = None,
    intent: str | None = None,
    title: str = "AlleleForge design report",
    top_alleles: int = 3,
    with_oligos: bool = True,
    scheme: VectorScheme | None = None,
) -> DesignReport:
    """Assemble a :class:`RankedMenu` into a serializable :class:`DesignReport`.

    Args:
        menu: The ranked menu to report on.
        variant: The target variant string (falls back to provenance if absent).
        intent: The edit intent (falls back to provenance if absent).
        title: Report title.
        top_alleles: How many outcome alleles to surface per candidate.
        with_oligos: Attach cloning-ready oligos to each candidate.
        scheme: Override the cloning scheme (defaults are per-chemistry).

    Returns:
        A :class:`DesignReport` with the disclaimer, per-candidate rows, and
        provenance.
    """
    snapshot = menu.provenance.config_snapshot if menu.provenance is not None else {}
    if intent is None:
        intent = snapshot.get("intent")
    weights = snapshot.get("weights", {})
    front = set(menu.pareto_front)
    candidates = tuple(
        _candidate_report(
            candidate,
            rank=i + 1,
            on_pareto_front=i in front,
            top_alleles=top_alleles,
            with_oligos=with_oligos,
            scheme=scheme,
        )
        for i, candidate in enumerate(menu.candidates)
    )
    return DesignReport(
        title=title,
        disclaimer=RESEARCH_USE_DISCLAIMER,
        variant=variant,
        intent=intent,
        weights=weights,
        candidates=candidates,
        provenance=menu.provenance,
    )
