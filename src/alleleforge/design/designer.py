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
from alleleforge.design.base_editor import (
    BaseOutcomePredictor,
    base_editor_model_checkpoints,
    design_base_editor,
)
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
from alleleforge.types.provenance import DatasetVersion, ModelCheckpoint, Provenance
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
    base_outcome_predictor: BaseOutcomePredictor | None = None,
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
        base_outcome_predictor: Override the base-edit window-outcome predictor (e.g.
            the opt-in trained BE-DICT model); default is the weight-free baseline.
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
            outcome_predictor=base_outcome_predictor,
            gnomad=gnomad,
            haplotypes=haplotypes,
            patient_vcf=patient_vcf,
            populations=populations,
            run_offtarget=run_offtarget,
            max_candidates=None,  # cap deferred to the composite ranker
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
                    max_candidates=None,  # cap deferred to the composite ranker
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
                    max_candidates=None,  # cap deferred to the composite ranker
                ),
                notes,
            )
        )

    outcome = rank_candidates(
        candidates, weights=weights, max_per_chemistry=max_candidates_per_chemistry
    )
    rationale = _menu_rationale(decisions, eligible, notes, outcome.rationale)
    provenance = Provenance.capture(
        alleleforge_version=__version__,
        seed=cfg.seed,
        reference_build=reference.build or build,
        timestamp=timestamp,
        models=_collect_model_checkpoints(
            eligible,
            cas9_efficiency_scorer=cas9_efficiency_scorer,
            cas9_outcome_predictor=cas9_outcome_predictor,
            base_outcome_predictor=base_outcome_predictor,
        ),
        datasets=_collect_datasets(reference, gnomad, clinvar),
        config_snapshot={
            "intent": intent.value,
            "weights": outcome.weights,
            "populations": list(populations) if populations else [],
            "run_offtarget": run_offtarget,
            "cell_context": cell_context,
            # The full resolved settings (minus volatile paths) so the run is
            # re-derivable from what actually governed it, not a subset that drifts.
            "settings": cfg.snapshot(),
        },
    )
    return RankedMenu(
        candidates=outcome.candidates,
        rationale=rationale,
        pareto_front=outcome.pareto_front,
        provenance=provenance,
    )


#: Exceptions that mean a chemistry legitimately produced no design (a missing
#: model, an unsupported edit, a bad input, an absent optional dependency) — the
#: graceful-degradation path. Any *other* exception type signals a defect in the
#: code, not "no design", and is noted distinctly so a real bug is not silently
#: swallowed behind an "eligible but empty" note.
_EXPECTED_DESIGN_FAILURES: tuple[type[Exception], ...] = (
    ValueError,
    KeyError,
    RuntimeError,
    NotImplementedError,
    FileNotFoundError,
    ImportError,
    OSError,
)


def _run_chemistry(label: str, runner: _Runner, notes: list[str]) -> list[DesignCandidate]:
    """Run one chemistry's vertical, degrading gracefully on an expected failure.

    An *expected* failure (see :data:`_EXPECTED_DESIGN_FAILURES`) is recorded as a
    ``skipped`` note; an *unexpected* exception type is a defect and is recorded as
    an ``ERROR`` note (still without crashing the whole design) so it is
    distinguishable from a legitimate "no design" rather than masked by graceful
    degradation.

    Args:
        label: The chemistry label for notes.
        runner: A zero-argument callable returning the chemistry's candidates.
        notes: Mutable note list the outcome (or failure reason) is appended to.

    Returns:
        The chemistry's candidates, or an empty list if it failed or found none.
    """
    try:
        result = runner()
    except _EXPECTED_DESIGN_FAILURES as exc:
        notes.append(f"{label}: skipped ({type(exc).__name__}: {exc})")
        return []
    except Exception as exc:  # noqa: BLE001 - a defect is surfaced, not swallowed as "no design"
        notes.append(
            f"{label}: ERROR — unexpected {type(exc).__name__}: {exc} (a defect, not 'no design')"
        )
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
    outcome_predictor: BaseOutcomePredictor | None,
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
            outcome_predictor=outcome_predictor,
            gnomad=gnomad,
            haplotypes=haplotypes,
            patient_vcf=patient_vcf,
            populations=populations,
            run_offtarget=run_offtarget,
            max_candidates=max_candidates,
        ),
        notes,
    )


def _collect_datasets(
    reference: ReferenceGenome,
    gnomad: GnomadDB | None,
    clinvar: ClinVarLookup | None,
) -> tuple[DatasetVersion, ...]:
    """Return the deduped dataset versions the run actually consumed.

    The dataset-capture helpers exist but were never wired into the design path,
    so a menu's provenance under-reported its own inputs. This mirrors
    :func:`_collect_model_checkpoints` for datasets: the reference build's
    :class:`DatasetVersion` (present when the reference was resolved through a
    pinned build) is recorded, and gnomAD/ClinVar are recorded when they carry a
    version descriptor, so no result silently omits a dataset it read. Deduped by
    ``(name, version)``.
    """
    seen: dict[tuple[str, str], DatasetVersion] = {}
    for source in (reference, gnomad, clinvar):
        version = getattr(source, "dataset_version", None)
        if isinstance(version, DatasetVersion):
            seen.setdefault((version.name, version.version), version)
    return tuple(seen.values())


def _collect_model_checkpoints(
    eligible: Sequence[Chemistry],
    *,
    cas9_efficiency_scorer: Cas9EfficiencyScorer | None = None,
    cas9_outcome_predictor: Cas9OutcomePredictor | None = None,
    base_outcome_predictor: BaseOutcomePredictor | None = None,
) -> tuple[ModelCheckpoint, ...]:
    """Return the deduped model checkpoints for every eligible chemistry's scorers.

    The models invoked are determined by which chemistries were eligible *and* by
    any scorer overrides the caller passed to ``design`` — the opt-in trained Rule
    Set 3 / Lindel / BE-DICT models. Each override's own card is recorded (falling
    back to the vertical's default when it is ``None``), so provenance names the
    model that actually scored the candidates rather than the default it replaced;
    otherwise a re-run from the stamped provenance would reproduce different
    numbers. Each contributing checkpoint is stamped into the menu's provenance
    block; a model shared across chemistries (keyed by name + version) is recorded
    once.
    """
    seen: dict[tuple[str, str], ModelCheckpoint] = {}
    contributors: list[tuple[bool, Callable[[], tuple[ModelCheckpoint, ...]]]] = [
        (
            bool(_BASE_CHEMISTRIES.intersection(eligible)),
            lambda: base_editor_model_checkpoints(base_outcome_predictor),
        ),
        (Chemistry.PRIME in eligible, prime_model_checkpoints),
        (
            Chemistry.CAS9_NUCLEASE in eligible,
            lambda: cas9_model_checkpoints(cas9_efficiency_scorer, cas9_outcome_predictor),
        ),
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
