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


#: Flags that change what a reader should *do*, each with the reason, keyed by the
#: prefix the emitting code uses (several carry a value after a colon).
#:
#: A candidate's flags are a flat list of free-form annotations, and every render
#: printed them as one comma-separated line — so a top-ranked pegRNA whose second nick
#: sits 8 nt away, effectively a staggered double-strand break, announced `close-nick`
#: with exactly the weight of `epegRNA:tevopreQ1`. The oligo *warnings* already have a
#: prominent channel for this reason (a donor that can be re-cut, an oligo too long to
#: synthesize); the candidate's own hazards did not, so they are separated here.
#:
#: Separated, not filtered: `CandidateReport.flags` still carries the complete list.
CAVEAT_FLAGS: dict[str, str] = {
    "ood": (
        "the efficiency prediction is out of distribution for this model — it is ranked "
        "on its lower interval bound, and the point estimate should not be trusted"
    ),
    "close-nick": (
        "the two nicks are close enough to act as a staggered double-strand break, the "
        "outcome prime editing is chosen to avoid; expect indel byproducts"
    ),
    "gc-out-of-band": (
        "spacer GC is outside the band where U6 transcription and oligo synthesis behave"
    ),
    "hdr-donor:recut-not-blocked": (
        "the repaired allele is still a substrate for this guide, so the correction can "
        "be cut again after repair"
    ),
    "outcome-is-nhej-spectrum": (
        "the outcome distribution below is the NHEJ indel spectrum — the byproduct of "
        "this strategy, not the intended correction, which is the minority product"
    ),
    "bystander-present": ("editable bystander bases sit in the window alongside the target"),
    "population-offtarget": (
        "at least one nominated off-target site exists only on a population allele, not "
        "in the reference"
    ),
    "relaxed-pam": (
        "a non-canonical PAM was accepted; activity and the off-target profile differ from NGG"
    ),
    "recommend-reference": (
        "this locus is ambiguous in the current build; the named assembly resolves it"
    ),
    "internal-": (
        "the reagent contains an internal site for the cloning enzyme, which will cut "
        "the insert — this scheme cannot be used as-is"
    ),
}

#: Flags that describe the candidate without asking anything of the reader. Listed
#: explicitly, not inferred, so a new flag has to be classified rather than silently
#: defaulting to "harmless" — the direction that loses a hazard.
DESCRIPTIVE_FLAGS: frozenset[str] = frozenset(
    {
        "both-nicks-searched",
        "clean",
        "hdr-donor:none",
        "hdr-donor:recut-blocked",
        "no-5prime-g",  # the cloning scheme prepends the U6-start G automatically
        "pe3",
        "pe3b",
        "no-nick",
        "epegRNA",
        "nick-distance",
        "templated-edit",
        "bystander-burden",
        "recommended",  # the cleanest base-editor candidate; a label, not a hazard
    }
)


def caveats(flags: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    """Return ``(flag, why it matters)`` for each flag that asks something of the reader.

    Args:
        flags: A candidate's complete flag list.

    Returns:
        Pairs in :data:`CAVEAT_FLAGS` order, so two candidates list their caveats the
        same way and a render is stable.
    """
    out: list[tuple[str, str]] = []
    for prefix, reason in CAVEAT_FLAGS.items():
        for flag in flags:
            if flag == prefix or flag.startswith(
                prefix if prefix.endswith(("-", ":")) else prefix + ":"
            ):
                out.append((flag, reason))
                break
    return tuple(out)


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
        n_outcome_alleles: How many alleles the predicted distribution holds in total.
        outcome_shown_mass: The probability mass ``outcome_top`` accounts for. An NHEJ
            spectrum is a long tail — a knock-out reporting ``P(intended) = 0.87`` above
            three rows of 0.069, 0.060 and 0.055 looks self-contradictory until the
            table says it is showing three of forty-one. The candidate list already
            says "Showing 50 of 470"; this is the same statement for the outcomes.
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
    n_outcome_alleles: int = 0
    outcome_shown_mass: float = 0.0
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
    n_outcome_alleles = 0
    outcome_shown_mass = 0.0
    p_intended: float | None = None
    if candidate.outcome is not None:
        ordered = sorted(candidate.outcome.alleles, key=lambda a: a.probability, reverse=True)
        outcome_top = tuple(ordered[:top_alleles])
        n_outcome_alleles = len(ordered)
        outcome_shown_mass = sum(a.probability for a in outcome_top)
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
        n_outcome_alleles=n_outcome_alleles,
        outcome_shown_mass=outcome_shown_mass,
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


def model_limitation_lines(provenance: Provenance | None) -> list[str]:
    """Return per-model limitation lines: what a model is not for, and how it fails.

    ``ModelCheckpoint`` carries these so a result is self-contained for safety audit
    "without re-opening the cards" — and no human-facing render printed any of them,
    so the audit still required re-opening the cards. A footer naming a model by
    version says which weights ran; it does not tell a reader that the model was
    never meant for this chemistry.

    Returns one line per model that documents something, formatted for a caller to
    escape and wrap for its own medium. Empty when no model documents a limitation,
    so a render can omit the section rather than print an empty heading.
    """
    if provenance is None:
        return []
    lines: list[str] = []
    for model in provenance.models:
        parts: list[str] = []
        if model.out_of_scope_use:
            parts.append(f"not for: {model.out_of_scope_use}")
        if model.known_failure_modes:
            parts.append("known failure modes: " + "; ".join(model.known_failure_modes))
        if parts:
            lines.append(f"{model.name} {model.version} — " + " | ".join(parts))
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
