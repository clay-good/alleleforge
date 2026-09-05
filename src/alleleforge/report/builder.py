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
        line = (
            f"SpCas9 sgRNA {g.spacer.sequence} "
            f"({g.pam.pattern} PAM, {g.placement.strand.value} strand, cut {g.cut_site})"
        )
        # A precise nuclease candidate is a *pair*: the guide and its repair
        # template. Naming only the guide would describe half a reagent and read
        # as a correction the break alone cannot make.
        donor = candidate.hdr_donor
        if donor is not None:
            recut = "re-cut blocked" if donor.recut_blocked else "re-cut NOT blocked"
            line += f" + HDR donor {len(donor.sequence)} nt ({recut})"
        return line
    if candidate.base_edit_window is not None:
        w = candidate.base_edit_window
        return f"{w.editor} sgRNA {w.spacer.sequence} (window {w.window[0]}-{w.window[1]})"
    if candidate.pegrna is not None:
        p = candidate.pegrna
        ng = p.nicking_guide
        nick = "PE3b" if (ng and ng.seed_disrupting) else ("PE3" if ng else "PE2")
        # ...and how far away that second nick is. It is the parameter PE3 design turns
        # on, and without it two PE3 candidates read identically on this line.
        if ng is not None:
            nick += f" ({ng.nick_offset:+d} nt nick)"
        # State what the RT template *writes*, not only how long it is: a pegRNA
        # correcting a 3-bp deletion and one installing a substitution differ in
        # nothing else on this line, and they are very different reagents.
        return (
            f"pegRNA spacer {p.spacer.sequence}; PBS {len(p.pbs)} nt / "
            f"RTT {len(p.rtt)} nt writing {p.templated_edit_length} nt; "
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
        offtarget_scorer: Name of the specificity scorer that produced the site
            scores (e.g. ``"CFD"``), so a reader can tell which scorer was used.
        offtarget_matrix: Identity of the weight source the scorer used (published
            CFD versus the labeled approximation), so a reader can tell the scoring
            basis without inspecting the code.
        offtarget_search: One-line statement of the budgets and cut-offs the search
            ran under. ``n_offtarget_sites`` and ``offtarget_specificity`` are both
            conditional on them — the same guide yields two sites at a 0.20 CFD
            cut-off and fifteen at 0.05 — so a report that shows the counts without
            them cannot be compared with another report.
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
    offtarget_scorer: str | None = None
    offtarget_matrix: str | None = None
    offtarget_search: str | None = None
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
        rationale: The **menu-level** rationale — which chemistries routed and why,
            which ran, and any that were skipped or failed. Without it a report can
            be empty with no explanation anywhere in it: the designer degrades
            gracefully when one chemistry fails, records exactly what happened here,
            and every renderer would otherwise drop it.
        provenance: The menu's provenance block (ends every render).
    """

    model_config = ConfigDict(frozen=True)

    title: str
    disclaimer: str
    variant: str | None
    intent: str | None
    weights: dict[str, float]
    candidates: tuple[CandidateReport, ...]
    rationale: str | None = None
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
    offtarget_scorer: str | None = None
    offtarget_matrix: str | None = None
    offtarget_search: str | None = None
    if candidate.offtarget is not None:
        n_sites = candidate.offtarget.n_sites
        specificity = candidate.offtarget.specificity_score()
        offtarget_scorer = candidate.offtarget.scorer
        offtarget_search = candidate.offtarget.search_description()
        # The *effective* matrix the reported sites were scored by, reconciled from
        # the per-site fallbacks — so an all-bulge/off-length table is not labeled
        # published CFD when every displayed score is the approximation.
        offtarget_matrix = candidate.offtarget.effective_matrix()
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
        offtarget_scorer=offtarget_scorer,
        offtarget_matrix=offtarget_matrix,
        offtarget_search=offtarget_search,
        oligos=oligos,
        oligos_requested=with_oligos,
        flags=candidate.flags,
        rationale=candidate.rationale,
    )


#: Default cap on how many candidates a *human-facing* render draws. A prime
#: design routinely yields several hundred — every PBS x RTT-homology x PAM
#: combination is a distinct pegRNA — which makes a "self-contained" page or PDF
#: run to megabytes for a tail nobody reads. The lossless exports ignore this.
DEFAULT_RENDER_CANDIDATES = 50


def visible_candidates(
    report: DesignReport, limit: int | None
) -> tuple[list[CandidateReport], int]:
    """Return the candidates a capped render should draw, and how many it withheld.

    The top ``limit`` by rank are kept, **plus every Pareto-front candidate**
    regardless of rank. The front is the report's whole answer to "I weight the
    objectives differently from your defaults", so a display cap must not be
    allowed to decide it away — a candidate that is optimal on safety but 200th on
    the composite score is exactly the one such a reader came for. Shared by the
    HTML and PDF renders so the two cannot drift apart on that guarantee.
    """
    if limit is None or len(report.candidates) <= limit:
        return list(report.candidates), 0
    kept = list(report.candidates[:limit])
    ranks = {c.rank for c in kept}
    kept += [c for c in report.candidates[limit:] if c.on_pareto_front and c.rank not in ranks]
    kept.sort(key=lambda c: c.rank)
    return kept, len(report.candidates) - len(kept)


#: Provenance fields the footer deliberately does not print, with the reason. The
#: footer is a curated summary, not a dump — but every omission must be a decision.
#: :func:`provenance_lines` and its coverage test read this, so adding a field to
#: :class:`~alleleforge.types.provenance.Provenance` forces a choice between rendering
#: it and naming it here.
PROVENANCE_FOOTER_OMITTED: dict[str, str] = {
    # Already rendered in full above the footer: the intent, weights and the settings
    # that scoped the run each appear beside the results they qualify.
    "config_snapshot": "rendered inline beside the results, not repeated in the footer",
}


def provenance_lines(provenance: Provenance | None) -> list[str]:
    """Return the provenance footer as plain-text lines, one fact per line.

    Shared by every render so the HTML page and the printable PDF cannot disagree
    about what a result's provenance says — they had already drifted on the wording
    for the reference build, and each would have had to grow the same field twice.

    Args:
        provenance: The menu's provenance block, or ``None``.

    Returns:
        Escaping-free lines the caller formats for its own medium.
    """
    if provenance is None:
        return []
    lines = [
        f"AlleleForge {provenance.alleleforge_version}",
        f"reference build {provenance.reference_build}",
        f"seed {provenance.seed}",
        f"generated {provenance.timestamp.isoformat()}",
    ]
    if provenance.models:
        lines.append("models: " + ", ".join(f"{m.name} {m.version}" for m in provenance.models))
    # The datasets are what the safety claims rest on — which gnomAD release stratified
    # the ancestries, which reference the coordinates are in, whether a patient VCF was
    # applied. A footer that names the models and not the data says which code ran but
    # not what it ran on, and "population-aware" is a claim about the data.
    if provenance.datasets:
        lines.append("datasets: " + ", ".join(f"{d.name} {d.version}" for d in provenance.datasets))
    if provenance.tools:
        lines.append("tools: " + ", ".join(f"{t.name} {t.version}" for t in provenance.tools))
    return lines


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
        variant: The target variant string, recorded verbatim (no provenance
            fallback — the config snapshot carries no variant field).
        intent: The edit intent (falls back to the provenance snapshot if absent).
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
        rationale=menu.rationale,
        provenance=menu.provenance,
    )
