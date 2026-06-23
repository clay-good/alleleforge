"""The designer: one variant in, a ranked multi-chemistry menu out.

:func:`design` is the orchestrator that realizes AlleleForge's variant-first
promise end to end:

1. **Resolve** any input form to one canonical variant (Phase 4).
2. **Route** to the chemistries that can biologically make the edit (routing).
3. **Enumerate and score** candidates from each eligible chemistry, each with a
   calibrated efficiency interval, a predicted outcome distribution, and an
   ancestry-stratified off-target report (Phases 5, 7-9).
4. **Rank** them on one footing with a transparent weighted sum and a Pareto
   front (ranking).
5. **Stamp provenance** so the whole menu is reproducible from its inputs.

The designer **degrades gracefully**: if a chemistry's model or enumeration
fails, or simply finds nothing actionable, the designer records *why* in the
menu rationale and continues with the rest. A returned menu therefore always
either carries a candidate per eligible chemistry or an explicit reason it does
not.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from datetime import datetime

from alleleforge._version import __version__
from alleleforge.config import Settings, get_settings
from alleleforge.data.gnomad import GnomadDB
from alleleforge.data.haplotypes import Haplotype
from alleleforge.design.base_editor import base_editor_model_checkpoints, design_base_editor
from alleleforge.design.cas9 import (
    Cas9EfficiencyScorer,
    Cas9OutcomePredictor,
    cas9_model_checkpoints,
    design_cas9,
)
from alleleforge.design.prime import design_prime, prime_model_checkpoints
from alleleforge.design.ranking import DEFAULT_WEIGHTS, RankingWeights, rank_candidates
from alleleforge.design.routing import ChemistryDecision, route
from alleleforge.enumerate.base_editor import BASE_EDITORS
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.candidate import DesignCandidate, RankedMenu
from alleleforge.types.edit import Chemistry, EditIntent
from alleleforge.types.provenance import ModelCheckpoint, Provenance
from alleleforge.types.variant import Variant
from alleleforge.variant.effect import EffectPredictor
from alleleforge.variant.hgvs_adapter import HgvsAdapter
from alleleforge.variant.resolver import (
    ClinVarLookup,
    DbSnpLookup,
    ResolvedVariant,
    ResolveInput,
    resolve,
)

#: Chemistries served by the base-editor vertical (one call covers both).
_BASE_CHEMISTRIES = frozenset({Chemistry.BASE_ABE, Chemistry.BASE_CBE})

#: A zero-argument chemistry runner returning that chemistry's candidates.
_Runner = Callable[[], list[DesignCandidate]]


def _resolve_input(
    inp: ResolveInput | ResolvedVariant,
    *,
    reference: ReferenceGenome,
    build: str,
    clinvar: ClinVarLookup | None,
    dbsnp: DbSnpLookup | None,
    hgvs: HgvsAdapter | None,
    effect: EffectPredictor | None,
) -> ResolvedVariant:
    """Resolve ``inp`` unless it is already a :class:`ResolvedVariant`."""
    if isinstance(inp, ResolvedVariant):
        return inp
    return resolve(
        inp,
        build=build,
        reference=reference,
        clinvar=clinvar,
        dbsnp=dbsnp,
        hgvs=hgvs,
        effect=effect,
    )


def design(
    inp: ResolveInput | ResolvedVariant,
    *,
    reference: ReferenceGenome,
    intent: EditIntent = EditIntent.CORRECT,
    chemistries: Sequence[Chemistry] | None = None,
    weights: RankingWeights = DEFAULT_WEIGHTS,
    populations: Sequence[str] | None = None,
    patient_vcf: Iterable[Variant] | None = None,
    gnomad: GnomadDB | None = None,
    haplotypes: Iterable[Haplotype] = (),
    cell_context: str | None = None,
    run_offtarget: bool = True,
    max_candidates_per_chemistry: int | None = None,
    build: str = "hg38",
    clinvar: ClinVarLookup | None = None,
    dbsnp: DbSnpLookup | None = None,
    hgvs: HgvsAdapter | None = None,
    effect: EffectPredictor | None = None,
    settings: Settings | None = None,
    timestamp: datetime | None = None,
    cas9_efficiency_scorer: Cas9EfficiencyScorer | None = None,
    cas9_outcome_predictor: Cas9OutcomePredictor | None = None,
) -> RankedMenu:
    """Design a ranked, multi-chemistry editing menu for a variant.

    Args:
        inp: Any resolver input form, or an already-:class:`ResolvedVariant`.
        reference: The reference genome.
        intent: What the edit must accomplish (default: ``CORRECT``).
        chemistries: Restrict to this subset of chemistries (default: every
            eligible chemistry). Ineligible requests are dropped with a note.
        weights: Ranking weights (default: the spec weights).
        populations: Ancestry labels to query and stratify off-target by.
        patient_vcf: Personal variants for off-target personalization.
        gnomad: gnomAD DB for population-aware off-target.
        haplotypes: Common haplotypes for haplotype-aware off-target.
        cell_context: Target cell context (prime efficiency OOD honesty).
        cas9_efficiency_scorer: Override the SpCas9 on-target efficiency scorer
            (e.g. the opt-in trained Rule Set 3 model); default is the weight-free
            deep ensemble.
        cas9_outcome_predictor: Override the SpCas9 indel-outcome predictor (e.g. the
            opt-in trained Lindel model); default is the microhomology baseline.
        run_offtarget: Run the off-target engine for every candidate.
        max_candidates_per_chemistry: Cap candidates kept from each chemistry.
        build: Reference build the input is expressed in.
        clinvar: ClinVar DB (needed for accession inputs).
        dbsnp: dbSNP DB (needed for rsID inputs).
        hgvs: HGVS adapter (needed for ``c.``/``p.`` inputs).
        effect: Effect predictor to annotate the variant's consequence.
        settings: Settings snapshot for provenance (default: the singleton).
        timestamp: Explicit provenance timestamp (for reproducible tests).

    Returns:
        A :class:`RankedMenu` ordered best-first across all chemistries, with the
        routing decisions, per-chemistry notes, ranking rationale, the Pareto
        front, and a full provenance block.
    """
    cfg = settings or get_settings()
    resolved = _resolve_input(
        inp,
        reference=reference,
        build=build,
        clinvar=clinvar,
        dbsnp=dbsnp,
        hgvs=hgvs,
        effect=effect,
    )

    requested = set(chemistries) if chemistries is not None else None
    decisions = route(resolved, intent)
    eligible: list[Chemistry] = []
    notes: list[str] = []
    for decision in decisions:
        if not decision.eligible:
            continue
        if requested is not None and decision.chemistry not in requested:
            notes.append(f"{decision.chemistry.value}: eligible but not requested")
            continue
        eligible.append(decision.chemistry)
    if requested is not None:
        eligible_chemistries = {d.chemistry for d in decisions if d.eligible}
        # sorted() so the note order is deterministic — a bare set-difference
        # iteration is hash-seed-ordered and would make the serialized menu
        # rationale vary run to run.
        for chem in sorted(requested - eligible_chemistries, key=lambda c: c.value):
            notes.append(f"{chem.value}: requested but not eligible for this variant/intent")

    candidates: list[DesignCandidate] = []
    candidates.extend(
        _run_base_editors(
            resolved,
            intent,
            eligible,
            reference=reference,
            gnomad=gnomad,
            haplotypes=haplotypes,
            patient_vcf=patient_vcf,
            populations=populations,
            run_offtarget=run_offtarget,
            max_candidates=max_candidates_per_chemistry,
            notes=notes,
        )
    )
    if Chemistry.PRIME in eligible:
        candidates.extend(
            _run_chemistry(
                "prime",
                lambda: design_prime(
                    resolved,
                    intent,
                    reference=reference,
                    cell_context=cell_context,
                    gnomad=gnomad,
                    haplotypes=haplotypes,
                    patient_vcf=patient_vcf,
                    populations=populations,
                    run_offtarget=run_offtarget,
                    max_candidates=max_candidates_per_chemistry,
                ),
                notes,
            )
        )
    if Chemistry.CAS9_NUCLEASE in eligible:
        candidates.extend(
            _run_chemistry(
                "cas9_nuclease",
                lambda: design_cas9(
                    resolved,
                    intent,
                    reference=reference,
                    efficiency_scorer=cas9_efficiency_scorer,
                    outcome_predictor=cas9_outcome_predictor,
                    gnomad=gnomad,
                    haplotypes=haplotypes,
                    patient_vcf=patient_vcf,
                    populations=populations,
                    run_offtarget=run_offtarget,
                    max_candidates=max_candidates_per_chemistry,
                ),
                notes,
            )
        )

    outcome = rank_candidates(candidates, weights=weights)
    rationale = _menu_rationale(decisions, eligible, notes, outcome.rationale)
    provenance = Provenance.capture(
        alleleforge_version=__version__,
        seed=cfg.seed,
        reference_build=reference.build or build,
        timestamp=timestamp,
        models=_collect_model_checkpoints(eligible),
        config_snapshot={
            "intent": intent.value,
            "weights": outcome.weights,
            "populations": list(populations) if populations else [],
            "run_offtarget": run_offtarget,
            "cell_context": cell_context,
        },
    )
    return RankedMenu(
        candidates=outcome.candidates,
        rationale=rationale,
        pareto_front=outcome.pareto_front,
        provenance=provenance,
    )


def _run_chemistry(label: str, runner: _Runner, notes: list[str]) -> list[DesignCandidate]:
    """Run one chemistry's vertical, degrading gracefully on any failure.

    Args:
        label: The chemistry label for notes.
        runner: A zero-argument callable returning the chemistry's candidates.
        notes: Mutable note list the outcome (or failure reason) is appended to.

    Returns:
        The chemistry's candidates, or an empty list if it failed or found none.
    """
    try:
        result = runner()
    except Exception as exc:  # noqa: BLE001 - graceful degradation is the contract
        notes.append(f"{label}: skipped ({type(exc).__name__}: {exc})")
        return []
    if not result:
        notes.append(f"{label}: eligible but no actionable candidate enumerated")
    else:
        notes.append(f"{label}: {len(result)} candidate(s)")
    return result


def _run_base_editors(
    resolved: ResolvedVariant,
    intent: EditIntent,
    eligible: list[Chemistry],
    *,
    reference: ReferenceGenome,
    gnomad: GnomadDB | None,
    haplotypes: Iterable[Haplotype],
    patient_vcf: Iterable[Variant] | None,
    populations: Sequence[str] | None,
    run_offtarget: bool,
    max_candidates: int | None,
    notes: list[str],
) -> list[DesignCandidate]:
    """Run the base-editor vertical once for whichever BE chemistries are eligible."""
    chosen = _BASE_CHEMISTRIES.intersection(eligible)
    if not chosen:
        return []
    editors = tuple(e for e in BASE_EDITORS if e.chemistry in chosen)
    return _run_chemistry(
        "+".join(sorted(c.value for c in chosen)),
        lambda: design_base_editor(
            resolved,
            intent,
            reference=reference,
            editors=editors,
            gnomad=gnomad,
            haplotypes=haplotypes,
            patient_vcf=patient_vcf,
            populations=populations,
            run_offtarget=run_offtarget,
            max_candidates=max_candidates,
        ),
        notes,
    )


def _collect_model_checkpoints(eligible: Sequence[Chemistry]) -> tuple[ModelCheckpoint, ...]:
    """Return the deduped model checkpoints for every eligible chemistry's scorers.

    ``design`` always runs each vertical with its default, card-backed scorers, so
    the models invoked are fully determined by which chemistries were eligible.
    Each contributing checkpoint is stamped into the menu's provenance block; a
    model shared across chemistries (keyed by name + version) is recorded once.
    """
    seen: dict[tuple[str, str], ModelCheckpoint] = {}
    contributors: list[tuple[bool, Callable[[], tuple[ModelCheckpoint, ...]]]] = [
        (bool(_BASE_CHEMISTRIES.intersection(eligible)), base_editor_model_checkpoints),
        (Chemistry.PRIME in eligible, prime_model_checkpoints),
        (Chemistry.CAS9_NUCLEASE in eligible, cas9_model_checkpoints),
    ]
    for is_eligible, checkpoints in contributors:
        if not is_eligible:
            continue
        for ckpt in checkpoints():
            seen.setdefault((ckpt.name, ckpt.version), ckpt)
    return tuple(seen.values())


def _menu_rationale(
    decisions: list[ChemistryDecision],
    eligible: list[Chemistry],
    notes: list[str],
    ranking_rationale: str,
) -> str:
    """Assemble the menu-level rationale from routing, notes, and ranking."""
    routed = ", ".join(f"{d.chemistry.value}={'yes' if d.eligible else 'no'}" for d in decisions)
    eligible_str = ", ".join(c.value for c in eligible) or "none"
    lines = [
        f"Routing: {routed}.",
        f"Eligible and run: {eligible_str}.",
        *(f"- {note}" for note in notes),
        ranking_rationale,
    ]
    return "\n".join(lines)
