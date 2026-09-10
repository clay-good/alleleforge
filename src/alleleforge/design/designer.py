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

from collections.abc import Callable, Collection, Iterable, Iterator, Sequence
from datetime import datetime

from alleleforge._version import __version__
from alleleforge.benchmark._canon import content_hash
from alleleforge.config import Settings, get_settings
from alleleforge.data.annotations import EncodeTracks
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
from alleleforge.design.prime import (
    PrimeEfficiencyScorer,
    design_prime,
    prime_model_checkpoints,
)
from alleleforge.design.ranking import DEFAULT_WEIGHTS, RankingWeights, rank_candidates
from alleleforge.design.routing import ChemistryDecision, route
from alleleforge.enumerate.base_editor import BASE_EDITORS
from alleleforge.enumerate.base_editor import rejection_summary as base_rejection_summary
from alleleforge.enumerate.prime import rejection_summary
from alleleforge.errors import (
    ChecksumError,
    ConsentError,
    MissingDependencyError,
    reason,
)
from alleleforge.genome.index import GenomeIndex
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.model_zoo.registry import CardError, LicenseError
from alleleforge.offtarget.cache import OffTargetCache
from alleleforge.scoring.prime_outcome import PrimeOutcomePredictor
from alleleforge.types.candidate import DesignCandidate, RankedMenu
from alleleforge.types.edit import Chemistry, EditIntent
from alleleforge.types.provenance import DatasetVersion, ModelCheckpoint, Provenance
from alleleforge.types.sequence import GenomicInterval
from alleleforge.types.variant import ClinicalSignificance, Variant, assembly_matches
from alleleforge.variant.effect import EffectPredictor, Impact
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


def model_chemistry_group(chemistry: Chemistry) -> frozenset[Chemistry]:
    """Return the chemistries that share one set of model checkpoints with ``chemistry``.

    :func:`_collect_model_checkpoints` groups its three contributors this way — the base
    vertical is one call covering ABE and CBE, and the single card it stamps is tagged
    ``base_abe``. So "does provenance name a model for this candidate's chemistry" cannot
    be answered by comparing the two labels directly: a genuine CBE candidate is scored
    by a checkpoint tagged ABE, and a checker that did not know it would refuse real
    output. Stated here so `aforge verify` reads the grouping off the same place the
    producer does rather than restating it.
    """
    return _BASE_CHEMISTRIES if chemistry in _BASE_CHEMISTRIES else frozenset({chemistry})


#: A zero-argument chemistry runner returning that chemistry's candidates.
_Runner = Callable[[], list[DesignCandidate]]


def _agreed_build(build: str | None, reference: ReferenceGenome) -> str:
    """Return the build to resolve in, refusing one the reference contradicts.

    A reference carries the assembly it is, and ``build`` says which assembly the input's
    coordinates are in. When both are given and they disagree, exactly one of them is
    wrong and nothing downstream can tell which: the provenance took the reference's
    label, so a run asked for in one assembly came back stamped with another — and the
    same `chr7:5,530,601` is a different base in the two.

    Omitting ``build`` adopts the reference's label, which is why the default is ``None``
    rather than ``"hg38"``: a caller who labelled their genome mm39 and never touched
    ``build`` was resolving against the string "hg38".
    """
    label = reference.build
    if build is None:
        return label or "hg38"
    if label and not assembly_matches(build, label):
        raise ValueError(
            f"build={build!r} was given for a reference labelled {label!r}; one of the "
            "two is wrong, and the same coordinate is a different base in two "
            "assemblies. Pass the build the reference is, or a reference for that build"
        )
    return build


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
    """Resolve ``inp`` unless it is already a :class:`ResolvedVariant`.

    Raises:
        ValueError: If ``inp`` is already resolved and any resolver backend was
            supplied. Those four arguments are only ever read during resolution, so on
            this path they are inert — and inert in a way that reads as an answer:
            a menu run with an `effect` predictor that was never consulted is
            indistinguishable from one whose predictor found nothing to say.
    """
    if isinstance(inp, ResolvedVariant):
        supplied = [
            name
            for name, value in (
                ("clinvar", clinvar),
                ("dbsnp", dbsnp),
                ("hgvs", hgvs),
                ("effect", effect),
            )
            if value is not None
        ]
        if supplied:
            raise ValueError(
                f"{', '.join(supplied)} cannot take effect: the input is already a "
                "ResolvedVariant, so resolution is skipped and these backends are "
                "never consulted. Pass them to resolve() when you resolve the "
                "variant, or hand design() the unresolved input instead."
            )
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
    offtarget_regions: Sequence[GenomicInterval] | None = None,
    offtarget_cache: OffTargetCache | None = None,
    genome_index: GenomeIndex | None = None,
    encode_tracks: EncodeTracks | None = None,
    chromatin_track: str | None = None,
    cell_context: str | None = None,
    run_offtarget: bool = True,
    max_candidates_per_chemistry: int | None = None,
    build: str | None = None,
    clinvar: ClinVarLookup | None = None,
    dbsnp: DbSnpLookup | None = None,
    hgvs: HgvsAdapter | None = None,
    effect: EffectPredictor | None = None,
    settings: Settings | None = None,
    timestamp: datetime | None = None,
    cas9_efficiency_scorer: Cas9EfficiencyScorer | None = None,
    cas9_outcome_predictor: Cas9OutcomePredictor | None = None,
    base_outcome_predictor: BaseOutcomePredictor | None = None,
    prime_efficiency_scorer: PrimeEfficiencyScorer | None = None,
    prime_outcome_predictor: PrimeOutcomePredictor | None = None,
    allow_ng: bool = False,
    allow_spry: bool = False,
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
        offtarget_regions: Restrict the off-target search to these intervals
            (default: every contig). Scoping a whole-genome scan to a gene panel
            is usually what makes a run over a real reference practical.
        offtarget_cache: Cross-run store of reference-only scans. The engine
            consults it only where the result is a pure function of the reference —
            the default scorer and no population, haplotype or patient data — so an
            augmented run is always computed fresh.
        genome_index: Persistent memory-mapped FM-index for the reference scan, built
            once and reused across runs and guides. Identical hits either way.
        encode_tracks: Optional ENCODE accessibility tracks for the ePRIDICT-style
            open-chromatin efficiency adjustment (prime editing only).
        chromatin_track: Which track to read from ``encode_tracks``; both are
            required together for the adjustment to apply.
        cell_context: Target cell context (prime efficiency OOD honesty).
        cas9_efficiency_scorer: Override the SpCas9 on-target efficiency scorer
            (e.g. the opt-in trained Rule Set 3 model); default is the weight-free
            deep ensemble.
        cas9_outcome_predictor: Override the SpCas9 indel-outcome predictor (e.g. the
            opt-in trained Lindel model); default is the microhomology baseline.
        base_outcome_predictor: Override the base-edit window-outcome predictor (e.g.
            the opt-in trained BE-DICT model); default is the weight-free baseline.
        prime_efficiency_scorer: Override the prime-efficiency scorer with any
            per-pegRNA ``score(pegrna, ...)`` implementation; default is the
            geometry baseline. Note there is no drop-in *trained* prime scorer
            today: ``PridictEngineAdapter`` is the real PRIDICT2.0 path but exposes
            a sequence-level ``design()`` API rather than this protocol, and the
            ``DeepPrimeAdapter`` / ``GenETAdapter`` placeholders implement the
            protocol only to refuse.
        prime_outcome_predictor: Override the prime byproduct predictor; default is
            the geometry baseline.
        run_offtarget: Run the off-target engine for every candidate.
        allow_ng: Fall back to SpCas9-NG (NG) guides when no NGG guide is
            actionable. Off by default: an NG guide is a different reagent with
            different specificity, so it is offered rather than assumed.
            Consumed by SpCas9 nuclease design alone: prime and base editing take
            no PAM-flexible fallback, and the rationale says so when one is
            enabled and the nuclease vertical did not run.
        allow_spry: Fall back to SpRY (NRN/NYN) guides when neither NGG
            nor NG yields one. Off by default, for the same reason.
        max_candidates_per_chemistry: Cap candidates kept from each chemistry.
        build: Reference build the input is expressed in. Defaults to the
            label the reference carries; stating a different one is a
            ``ValueError``, not a run relabelled to the reference's.
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
    # `chromatin_track` names a track *inside* `encode_tracks`; without the tracks there
    # is nothing to name. Supplying only the name used to run to completion, record
    # `chromatin_track` in the provenance snapshot as though the run were
    # chromatin-aware, and then report "supplied but covers none of the candidate loci"
    # — which asserts a supply that never happened and sends the reader to inspect a
    # track file they do not have. The CLI refused the combination; every other caller
    # (the library, the cohort, the web API) did not.
    if chromatin_track is not None and encode_tracks is None:
        raise ValueError(
            f"chromatin_track {chromatin_track!r} was given without encode_tracks; the "
            "track name selects a track from the supplied ENCODE tracks, so both are "
            "required together (or pass neither for an unadjusted run)"
        )
    cfg = settings or get_settings()
    build = _agreed_build(build, reference)
    resolved = _resolve_input(
        inp,
        reference=reference,
        build=build,
        clinvar=clinvar,
        dbsnp=dbsnp,
        hgvs=hgvs,
        effect=effect,
    )

    # Materialize the one-shot safety inputs before fanning out. `design` hands each of
    # these to up to three verticals in turn, and to `_collect_datasets` — so a caller
    # passing a generator (both are typed `Iterable`) had it consumed by whichever
    # chemistry ran first, and every later chemistry searched without it.
    #
    # The failure is worse here than at the `search` level, because it is *per
    # chemistry*: one menu could hold haplotype-aware base-editor candidates beside
    # reference-only pegRNAs, screened differently, presented identically, ranked
    # against each other on a safety axis they did not share.
    # Only a true *iterator* is copied. `list()` unconditionally would strip the
    # provenance descriptor that `HaplotypePanel` and `_PatientVariants` carry as an
    # attribute — `_collect_datasets` reads it off these very objects, and the CLI's
    # `_load_haplotypes` docstring warns about exactly that flattening. A re-iterable
    # object is already safe to hand to three verticals; a generator is not.
    if isinstance(haplotypes, Iterator):
        haplotypes = list(haplotypes)
    if isinstance(patient_vcf, Iterator):
        patient_vcf = list(patient_vcf)

    requested = set(chemistries) if chemistries is not None else None
    decisions = route(resolved, intent)
    eligible: list[Chemistry] = []
    # Lead with what the database says about the target, before anything about
    # chemistry: a menu is only meaningful once the reader knows what is being edited.
    notes: list[str] = _clinical_notes(resolved, intent)
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
    # Chemistries whose vertical raised, so provenance does not stamp a model card for a
    # scorer that never scored anything. The note says "skipped"; the models block used
    # to say the model was there.
    failed: set[Chemistry] = set()
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
            offtarget_regions=offtarget_regions,
            offtarget_cache=offtarget_cache,
            genome_index=genome_index,
            populations=populations,
            run_offtarget=run_offtarget,
            max_candidates=None,  # cap deferred to the composite ranker
            notes=notes,
            failed=failed,
        )
    )
    if Chemistry.PRIME in eligible:
        # Prime is the flagship chemistry and the one most often eligible-but-empty:
        # a nick has to land within RTT reach of the edit, and no PAM in range may do
        # so. "eligible but no actionable candidate enumerated" tells a scientist that
        # and nothing else, when the reasons have different remedies — try the other
        # strand, a different PAM, another chemistry. Collect them; the tally costs a
        # dict increment per rejected protospacer and is only rendered when empty.
        prime_tally: dict[str, int] = {}
        candidates.extend(
            _run_chemistry(
                "prime",
                lambda: design_prime(
                    resolved,
                    intent,
                    reference=reference,
                    efficiency_scorer=prime_efficiency_scorer,
                    outcome_predictor=prime_outcome_predictor,
                    encode_tracks=encode_tracks,
                    chromatin_track=chromatin_track,
                    cell_context=cell_context,
                    gnomad=gnomad,
                    haplotypes=haplotypes,
                    patient_vcf=patient_vcf,
                    offtarget_regions=offtarget_regions,
                    offtarget_cache=offtarget_cache,
                    genome_index=genome_index,
                    populations=populations,
                    run_offtarget=run_offtarget,
                    max_candidates=None,  # cap deferred to the composite ranker
                    tally=prime_tally,
                ),
                notes,
                empty_reason=lambda: rejection_summary(prime_tally),
                chemistries=(Chemistry.PRIME,),
                failed=failed,
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
                    offtarget_regions=offtarget_regions,
                    offtarget_cache=offtarget_cache,
                    genome_index=genome_index,
                    populations=populations,
                    run_offtarget=run_offtarget,
                    max_candidates=None,  # cap deferred to the composite ranker
                    allow_ng=allow_ng,
                    allow_spry=allow_spry,
                ),
                notes,
                empty_reason=lambda: _cas9_empty_reason(allow_ng, allow_spry),
                chemistries=(Chemistry.CAS9_NUCLEASE,),
                failed=failed,
            )
        )

    # The resolver flags a locus overlapping a segmental duplication, centromere, or
    # other hg38-difficult region and recommends T2T. That recommendation reached the
    # `resolve` output and stopped there: `ReferenceRecommendation.apply_to` — its own
    # docstring calls it "the wiring point into the Phase 1 result types" — had no
    # caller in the package. So a design inside a segdup produced a full menu with
    # nothing on it saying that alignment here is ambiguous, which is exactly the
    # condition under which the off-target search under-reports.
    if resolved.reference_recommendation is not None:
        candidates = [resolved.reference_recommendation.apply_to(c) for c in candidates]

    enumerated = len(candidates)
    outcome = rank_candidates(
        candidates, weights=weights, max_per_chemistry=max_candidates_per_chemistry
    )
    # The run notes above report what each vertical *enumerated*. A per-chemistry cap
    # then drops candidates, and nothing said so: a menu of 2 carried the note
    # "cas9_nuclease: 23 candidate(s)", which reads as a count of the menu and is a
    # count of the pool. Unlike the render caps, this one removes them from the export
    # too, so there is no other copy to point at — the reader has to be told the number
    # above is not the number below, and what setting made the difference.
    dropped = enumerated - len(outcome.candidates)
    if dropped > 0:
        notes.append(
            f"--max-per-chemistry {max_candidates_per_chemistry}: the counts above are "
            f"what each chemistry enumerated; {dropped} lower-ranked candidate(s) were "
            "dropped and are not in this result or its exports"
        )
    # A chromatin track can be supplied, recorded in provenance, and cover none of the
    # candidate loci — leaving every efficiency unadjusted while the run reads as
    # chromatin-aware. Say so, for the same reason an inert population source is worth
    # saying: the artifact otherwise claims an input it did not use.
    if chromatin_track is not None and candidates:
        adjusted = sum(1 for c in candidates if "chromatin-adjusted" in c.flags)
        if adjusted == 0:
            notes.append(
                f"chromatin track {chromatin_track!r} was supplied but covers none of "
                "the candidate loci — every efficiency here is the unadjusted estimate"
            )
    # `cell_context` is consumed by the prime vertical alone -- SpCas9 nuclease and base
    # editing do not take it, so for those chemistries the supplied context is never
    # examined. Their `in_distribution` flag stays truthful about what it does measure
    # (the guide context: no ambiguous base, long enough for the head to read), and that
    # is exactly the problem: a reader who asked for K562 sees `in_distribution: True`
    # next to a nuclease candidate and reads it as a statement about K562. It is not one.
    # An unrecognized context makes this plainest -- prime flags `ood` and the other two
    # report in-distribution -- so name the chemistries that could not consider it.
    if cell_context is not None and candidates:
        unconsidered = sorted(
            {c.chemistry.value for c in candidates if c.chemistry is not Chemistry.PRIME}
        )
        if unconsidered:
            notes.append(
                f"cell context {cell_context!r} was supplied but is only consumed by prime "
                f"editing; it was not considered for {', '.join(unconsidered)}, whose "
                "in-distribution flags describe the guide context alone"
            )
    # The same declaration, for the same reason, on the PAM fallbacks. `--allow-ng` says
    # "fall back to SpCas9-NG guides when no NGG guide is actionable", which reads as a
    # statement about the run; it is routed to the SpCas9 nuclease vertical alone. A
    # reader who enabled it and got an empty *prime* menu — whose decline reason is a
    # bare "no PAM match at this offset" — has no way to learn the flag never applied
    # there. Extending it to prime is a scientific decision (a PE-NG/PE-SpRY pegRNA is a
    # different reagent, and the efficiency scorers are trained on SpCas9 PE2), so this
    # states the scope rather than quietly widening it.
    if (allow_ng or allow_spry) and Chemistry.CAS9_NUCLEASE not in eligible:
        enabled = ", ".join(
            name for on, name in ((allow_ng, "SpCas9-NG"), (allow_spry, "SpRY")) if on
        )
        notes.append(
            f"the PAM-flexible fallback(s) {enabled} were enabled but are consumed by "
            "SpCas9 nuclease design alone, which did not run here; no other chemistry "
            "offered a PAM-flexible alternative"
        )
    rationale = _menu_rationale(decisions, eligible, notes, outcome.rationale)
    provenance = Provenance.capture(
        alleleforge_version=__version__,
        seed=cfg.seed,
        reference_build=build,
        timestamp=timestamp,
        models=_collect_model_checkpoints(
            # Not `eligible`: a chemistry whose vertical raised scored nothing, and the
            # commonest way it raises is the trained model itself being refused (a
            # licence gate, a missing extra, an unverifiable checkpoint). Recording its
            # card said "this run used the model that was in fact turned away".
            [c for c in eligible if c not in failed],
            cas9_efficiency_scorer=cas9_efficiency_scorer,
            cas9_outcome_predictor=cas9_outcome_predictor,
            base_outcome_predictor=base_outcome_predictor,
            prime_efficiency_scorer=prime_efficiency_scorer,
            prime_outcome_predictor=prime_outcome_predictor,
        ),
        datasets=_collect_datasets(
            reference,
            gnomad,
            clinvar,
            # A haplotype panel and a patient variant set are inputs a result
            # depends on as much as gnomAD is; a run that used them and does not
            # name them is not re-derivable from its own provenance.
            # `dbsnp` belongs here for the same reason `clinvar` is named above: it
            # decides *which locus the run is about*. It was the one resolution input
            # with no route into provenance, so two runs off different dbSNP releases
            # — hence potentially different coordinates for one rsID — produced
            # byte-identical `datasets`.
            extra=(dbsnp, *resolved.sources, haplotypes, patient_vcf, encode_tracks),
            # The weight matrix every specificity number on the menu came out of. It
            # is a registered, sha-pinned, *bundled* dataset and it was the one input
            # a scored run never recorded: an off-target run reported `matrix
            # doench-2016-cfd` on every candidate and `0 dataset(s)` in provenance, so
            # `verify --cache-dir` could not re-hash the file that produced them.
            scored_matrices=_scored_matrices(candidates),
        ),
        config_snapshot={
            "intent": intent.value,
            "weights": outcome.weights,
            "populations": list(populations) if populations else [],
            "run_offtarget": run_offtarget,
            # `None` means the whole genome was searched. A *restricted* scan
            # reports far fewer sites than a genome-wide one, and without this the
            # two results are indistinguishable — "0 off-targets" would read the
            # same whether every contig or a 100 bp window was examined.
            "offtarget_regions": _regions_snapshot(offtarget_regions),
            # The genome searched is the largest single determinant of an
            # off-target result, and `reference_build` is only a *label* — it
            # stays "hg38" whatever FASTA was opened. Two runs over two different
            # references were otherwise byte-identical in provenance while their
            # specificity differed twofold.
            "reference": _reference_snapshot(reference),
            "cell_context": cell_context,
            # Result-determining inputs that were absent from the snapshot: each
            # changes what the menu *is*, not how it is displayed, so a re-run from
            # this record without them reproduces a different result.
            "chemistries": [c.value for c in chemistries] if chemistries else [],
            "max_candidates_per_chemistry": max_candidates_per_chemistry,
            "allow_ng": allow_ng,
            "allow_spry": allow_spry,
            "chromatin_track": chromatin_track,
            # The full resolved settings (minus volatile paths) so the run is
            # re-derivable from what actually governed it, not a subset that drifts.
            "settings": cfg.snapshot(),
        },
    )
    return RankedMenu(
        variant=str(resolved.variant),
        clinical_significance=(
            resolved.clinical_assertion.significance.value
            if resolved.clinical_assertion is not None
            else None
        ),
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
#:
#: `RuntimeError` used to be in this list and defeated that promise for the commonest
#: way a Python defect surfaces: a genuine bug in a vertical was reported with the same
#: word — "skipped" — as a chemistry that simply did not apply. It was there because the
#: gate refusals and the missing-dependency signals are all `RuntimeError` subclasses;
#: naming them individually keeps the graceful path and gives the base class back its
#: meaning. Deliberately absent: `FMIndexIntegrityError` and `CacheIntegrityError`, which
#: are corruption or tampering — degrading those to "skipped" would undo the fail-closed
#: gates that exist to catch them.
_EXPECTED_DESIGN_FAILURES: tuple[type[Exception], ...] = (
    ValueError,
    KeyError,
    NotImplementedError,
    FileNotFoundError,
    ImportError,
    OSError,
    ConsentError,
    ChecksumError,
    LicenseError,
    CardError,
    MissingDependencyError,
)


def _cas9_empty_reason(allow_ng: bool, allow_spry: bool) -> str:
    """Explain an empty Cas9 vertical, naming the PAM variants not tried.

    The enumerator can fall back to SpCas9-NG (`NG`) and SpRY (`NRN`/`NYN`) when no
    `NGG` guide is actionable, and both default to off — so the common outcome is "no
    NGG in range" reported as "nothing found", while the tool holds two published,
    widely used PAM-flexible options it did not mention. Naming them is the difference
    between a dead end and a next step.
    """
    tried = ["NGG"]
    if allow_ng:
        tried.append("NG (SpCas9-NG)")
    if allow_spry:
        tried.append("NRN/NYN (SpRY)")
    untried = [
        name
        for enabled, name in ((allow_ng, "NG (SpCas9-NG)"), (allow_spry, "NRN/NYN (SpRY)"))
        if not enabled
    ]
    reason = f"no actionable protospacer with a {' or '.join(tried)} PAM near the edit"
    if untried:
        reason += f"; the PAM-flexible variants {', '.join(untried)} were not enabled"
    return reason


#: The marker every unexpected-failure note carries, so a *shell* can tell a run that
#: degraded around a defect from one that simply found nothing. The notes are prose in
#: the menu's rationale and there is no structured field for them, so this constant is
#: the seam: `_run_chemistry` writes it and `aforge design` reads it to decide its exit
#: code, and `test_a_defect_note_is_the_marker_the_shell_reads` pins the two together so
#: rewording the note cannot silently un-fail the command.
DEFECT_NOTE = "ERROR — unexpected"


def _run_chemistry(
    label: str,
    runner: _Runner,
    notes: list[str],
    *,
    empty_reason: Callable[[], str] | None = None,
    chemistries: Collection[Chemistry] = (),
    failed: set[Chemistry] | None = None,
) -> list[DesignCandidate]:
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
        empty_reason: Called only when the runner returned nothing, to explain why.
        chemistries: The chemistries this vertical covers, for attributing a failure.
        failed: Mutable set the covered chemistries are added to when the runner
            raises. Provenance stamps a model card for every *eligible* chemistry, so
            a vertical that never ran — because its own trained scorer was refused by
            the licence gate, or could not load — still had its model recorded, and the
            artifact named a model that scored nothing. The note said "skipped" three
            lines above the provenance block that said otherwise.

    Returns:
        The chemistry's candidates, or an empty list if it failed or found none.
    """
    try:
        result = runner()
    except _EXPECTED_DESIGN_FAILURES as exc:
        notes.append(f"{label}: skipped ({type(exc).__name__}: {reason(exc)})")
        if failed is not None:
            failed.update(chemistries)
        return []
    except Exception as exc:  # noqa: BLE001 - a defect is surfaced, not swallowed as "no design"
        notes.append(
            f"{label}: {DEFECT_NOTE} {type(exc).__name__}: {reason(exc)} "
            "(a defect, not 'no design')"
        )
        if failed is not None:
            failed.update(chemistries)
        return []
    if not result:
        # Say *why* when the vertical can explain itself. "Nothing found" and "nothing
        # found because every nick in range is too far from the edit for a synthesizable
        # RTT" send a reader to different next steps, and only one of them is a dead end.
        why = f" — {empty_reason()}" if empty_reason is not None else ""
        notes.append(f"{label}: eligible but no actionable candidate enumerated{why}")
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
    offtarget_regions: Sequence[GenomicInterval] | None,
    offtarget_cache: OffTargetCache | None,
    genome_index: GenomeIndex | None,
    run_offtarget: bool,
    max_candidates: int | None,
    notes: list[str],
    failed: set[Chemistry] | None = None,
) -> list[DesignCandidate]:
    """Run the base-editor vertical once for whichever BE chemistries are eligible."""
    chosen = _BASE_CHEMISTRIES.intersection(eligible)
    if not chosen:
        return []
    editors = tuple(e for e in BASE_EDITORS if e.chemistry in chosen)
    # Same reasoning as the prime vertical: base editing's failure modes have different
    # remedies — no deaminase in the panel writes this substitution, the target base
    # sits outside every activity window, no PAM reaches it — and the first of those is
    # a fact about the *edit*, not the locus, which a reader should not infer from
    # silence.
    be_tally: dict[str, int] = {}
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
            offtarget_regions=offtarget_regions,
            offtarget_cache=offtarget_cache,
            genome_index=genome_index,
            populations=populations,
            run_offtarget=run_offtarget,
            max_candidates=max_candidates,
            tally=be_tally,
        ),
        notes,
        empty_reason=lambda: base_rejection_summary(be_tally),
        chemistries=tuple(chosen),
        failed=failed,
    )


def _regions_snapshot(
    regions: Sequence[GenomicInterval] | None,
) -> dict[str, object] | None:
    """Summarize an off-target region restriction for the provenance snapshot.

    ``None`` — the whole genome was searched. Otherwise a compact record: how many
    intervals, how many bases they cover, and a content hash of the canonicalized
    list, so a re-run can prove it used the same restriction without provenance
    carrying a whole BED file.
    """
    if regions is None:
        return None
    canonical = sorted(f"{r.chrom}:{r.start}-{r.end}" for r in regions)
    return {
        "n": len(canonical),
        "bases": sum(r.end - r.start for r in regions),
        "sha256": content_hash(canonical),
    }


def _reference_snapshot(reference: ReferenceGenome) -> dict[str, object]:
    """Describe the reference genome a run searched, for the provenance snapshot.

    A registry-resolved build already lands in ``datasets`` with its pinned hash,
    but the ordinary path — a local FASTA handed to ``--reference-fasta`` — carries
    no descriptor, so provenance named no genome at all. This mirrors
    :func:`_regions_snapshot`: a compact record rather than the input itself.

    What it pins is the reference's *shape* — contig names and lengths, read from
    the index, so the cost is O(contigs) rather than the size of the FASTA. Two
    references with the same contigs and lengths and different bases are
    indistinguishable to it, and ``pins`` says so, because a digest that overclaims
    its own reach is worse than one that does not exist.

    Args:
        reference: The opened reference genome.

    Returns:
        The build label, contig and base counts, a content hash of the
        canonicalized ``name:length`` list, and a statement of the extent.
    """
    lengths = reference.contig_lengths()
    canonical = sorted(f"{name}:{length}" for name, length in lengths.items())
    return {
        "build": reference.build,
        "contigs": len(lengths),
        "bases": sum(lengths.values()),
        "sha256": content_hash(canonical),
        "pins": "contig names and lengths, not the bases",
    }


def _scored_matrices(candidates: Sequence[DesignCandidate]) -> frozenset[str]:
    """Return the weight-matrix identities the candidates' reported sites were scored by.

    Read off the results rather than off the scorer's configuration: a fixed published
    matrix falls back to the length-relative approximation per hit, so what a run
    *consumed* is what its sites say, not what it was set to.
    """
    used: set[str] = set()
    for candidate in candidates:
        report = candidate.offtarget
        if report is None:
            continue
        effective = report.effective_matrix()
        if effective:
            used.update(part.strip() for part in effective.split("+"))
    return frozenset(used)


def _collect_datasets(
    reference: ReferenceGenome,
    gnomad: GnomadDB | None,
    clinvar: ClinVarLookup | None,
    *,
    extra: Sequence[object] = (),
    scored_matrices: frozenset[str] = frozenset(),
) -> tuple[DatasetVersion, ...]:
    """Return the deduped dataset versions the run actually consumed.

    The dataset-capture helpers exist but were never wired into the design path,
    so a menu's provenance under-reported its own inputs. This mirrors
    :func:`_collect_model_checkpoints` for datasets: the reference build's
    :class:`DatasetVersion` (present when the reference was resolved through a
    pinned build) is recorded, and gnomAD/ClinVar are recorded when they carry a
    version descriptor, so no result silently omits a dataset it read. ``extra``
    carries any further source the caller attached a descriptor to — a haplotype
    panel or a patient variant set, say — so a population/haplotype-aware run
    records *which* data made it so rather than only that it ran. Deduped by
    ``(name, version)``.
    """
    seen: dict[tuple[str, str], DatasetVersion] = {}
    for source in (reference, gnomad, clinvar, *extra):
        # A ready-made descriptor is accepted alongside an object carrying one: a
        # shell that resolves the variant itself (the CLI does) never hands the
        # design layer the lookup database, only the descriptor the resolved
        # variant carries, so without this the release that chose the locus went
        # unrecorded on every command-line run.
        version = source if isinstance(source, DatasetVersion) else None
        if version is None:
            candidate = getattr(source, "dataset_version", None)
            version = candidate if isinstance(candidate, DatasetVersion) else None
        if version is not None:
            seen.setdefault((version.name, version.version), version)
    # A scoring matrix is a dataset the run read, not a model it ran: it is registered,
    # pinned and cited like every other one. Only matrices the registry knows are
    # recorded — the length-relative approximation is code, has no bytes to pin, and is
    # already named per site and per candidate.
    from alleleforge.data.registry import DEFAULT_REGISTRY

    for matrix in sorted(scored_matrices):
        if matrix not in DEFAULT_REGISTRY:
            continue
        version = DEFAULT_REGISTRY.get(matrix).dataset_version()
        seen.setdefault((version.name, version.version), version)
    return tuple(seen.values())


def _collect_model_checkpoints(
    eligible: Sequence[Chemistry],
    *,
    cas9_efficiency_scorer: Cas9EfficiencyScorer | None = None,
    cas9_outcome_predictor: Cas9OutcomePredictor | None = None,
    base_outcome_predictor: BaseOutcomePredictor | None = None,
    prime_efficiency_scorer: PrimeEfficiencyScorer | None = None,
    prime_outcome_predictor: PrimeOutcomePredictor | None = None,
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
        (
            Chemistry.PRIME in eligible,
            lambda: prime_model_checkpoints(prime_efficiency_scorer, prime_outcome_predictor),
        ),
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


#: Significance classes for which a *correcting* edit has no clinical rationale, and an
#: *installing* edit is a deliberate disease model rather than a therapy. Stated as data
#: so the reasoning is inspectable, and used only to annotate — never to refuse. A user
#: correcting a benign variant may have a perfectly good reason (a research control, a
#: reclassification the database has not caught up with); they should simply not do it by
#: accident because nothing told them the database disagrees.
_BENIGN_CLASSES = frozenset({ClinicalSignificance.BENIGN, ClinicalSignificance.LIKELY_BENIGN})


def _clinical_notes(resolved: ResolvedVariant, intent: EditIntent) -> list[str]:
    """Return notes stating what is known about the target, and any tension with intent.

    Two facts a design is meaningless without, both of which the pipeline computed and
    then discarded: what a clinical database asserts about the variant (the reason an
    accession was chosen over coordinates) and its predicted molecular consequence
    (paid for with a network round trip and a decision to disclose the variant). A menu
    for a variant ClinVar calls Benign read exactly like a menu for a pathogenic one.

    State both, and say plainly when the requested intent and what is known pull in
    different directions. Every note here annotates; none refuses.
    """
    notes: list[str] = []
    effect = resolved.effect
    if effect is not None:
        notes.append(effect.describe())
        # A correction that changes no protein is worth a second look before the bench
        # work starts. Same disposition as the ClinVar notes below: annotate, never
        # refuse — a silent variant can still be a splice or regulatory target, and the
        # predictor only speaks for one transcript.
        if intent in (EditIntent.CORRECT, EditIntent.REVERT) and effect.impact is Impact.MODIFIER:
            notes.append(
                f"intent {intent.value} targets a variant predicted to have modifier "
                "impact on this transcript — confirm this is the change you mean to make"
            )
    assertion = resolved.clinical_assertion
    if assertion is None:
        return notes
    notes.append(assertion.describe())
    if intent in (EditIntent.CORRECT, EditIntent.REVERT):
        if assertion.significance in _BENIGN_CLASSES:
            notes.append(
                f"intent {intent.value} restores the reference at a variant ClinVar "
                f"classifies as {assertion.significance.value.replace('_', ' ')} — "
                "confirm the target is the allele you mean to change"
            )
        elif assertion.significance is ClinicalSignificance.UNCERTAIN:
            notes.append(
                f"intent {intent.value} targets a variant of uncertain significance; "
                "the correction is well defined but its clinical benefit is not asserted"
            )
    elif intent is EditIntent.INSTALL and assertion.significance in (
        ClinicalSignificance.PATHOGENIC,
        ClinicalSignificance.LIKELY_PATHOGENIC,
    ):
        notes.append(
            f"intent install writes an allele ClinVar classifies as "
            f"{assertion.significance.value.replace('_', ' ')} — a disease model, "
            "not a correction"
        )
    return notes


def _first_sentence(text: str) -> str:
    """Return ``text`` up to its first sentence end, or the whole of a short one.

    Used for the declined-chemistry lines that appear beside a non-empty menu. The
    routing rationales are written as full explanations — the SpCas9 one is a
    paragraph — and repeating that for every chemistry in every report drowns the
    candidates. The opening sentence carries the chemistry's role, which is what a
    reader asking "why not that one?" needs before deciding to look further.
    """
    stripped = text.strip()
    for end in (". ", ".\n"):
        head, sep, _ = stripped.partition(end)
        if sep:
            return head + "."
    return stripped


def _declined_line(decision: ChemistryDecision, *, brief: bool = False) -> str:
    """Render one declined chemistry: what closed the route, then the policy.

    The heading above these lines asks why the chemistry declined, and for a long
    time the answer under it was the rule's `rationale` — a description of what the
    chemistry is for, identical on every run, from which the reader was left to
    derive the comparison themselves. `decline_reason` is the half that is about
    their variant, so it leads.
    """
    policy = _first_sentence(decision.rationale) if brief else decision.rationale
    if decision.decline_reason is None:
        return policy  # a decision built without one; the policy is still true
    return f"{decision.decline_reason}. {policy}"


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
    ]
    declined = [d for d in decisions if d.chemistry not in eligible]
    if declined:
        # Always, not only when the menu is empty. The rationales are computed either
        # way and explain exactly which biological or budget constraint each chemistry
        # hit — and "base_abe=no" is least actionable precisely for the reader who
        # needed a base editor: someone avoiding a double-strand break, who now sees a
        # prime candidate and no statement of why the chemistry they wanted declined.
        # Full rationales when nothing is eligible — there the menu is empty and this
        # *is* the content. When something did succeed, the first sentence only: the
        # cas9 rationale runs to 540 characters, and a paragraph per declined chemistry
        # in every report buries the result the reader came for. The first sentence is
        # the one that names the chemistry's role and why it is or is not the route.
        if not eligible:
            lines.append("No chemistry can make this edit. Why each declined:")
            lines += [f"- {d.chemistry.value}: {_declined_line(d)}" for d in declined]
        else:
            lines.append("Why the other chemistries declined:")
            lines += [f"- {d.chemistry.value}: {_declined_line(d, brief=True)}" for d in declined]
    if notes:
        # Their own heading. These are run outcomes and caveats — what each eligible
        # chemistry produced, what the database says about the target, whether a
        # supplied track covered anything — and they were appended as bare `- ` bullets
        # directly under "Why the other chemistries declined:", in that list's format.
        # A reader met `- prime: 90 candidate(s)` as a reason prime declined, on a page
        # where prime produced every candidate.
        lines.append("Run notes:")
        lines += [f"- {note}" for note in notes]
    lines.append(ranking_rationale)
    return "\n".join(lines)
