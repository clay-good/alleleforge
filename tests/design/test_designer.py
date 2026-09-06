"""End-to-end tests for the Phase 10 designer orchestrator."""

from __future__ import annotations

import random
from collections.abc import Callable

import pytest

from alleleforge.data.haplotypes import Haplotype
from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.model_zoo.registry import ModelCard, default_registry
from alleleforge.types.candidate import RankedMenu
from alleleforge.types.edit import Chemistry, EditIntent
from alleleforge.types.guide import PegRNA
from alleleforge.types.prediction import Prediction, UncertaintyMethod
from alleleforge.types.provenance import Provenance
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.types.variant import ClinicalSignificance, ClinVarAccession, Variant
from alleleforge.variant.effect import Consequence, VariantEffect, impact_of
from alleleforge.variant.resolver import ResolvedVariant, resolve

MakeRef = Callable[[dict[str, str]], ReferenceGenome]
PAD = "T" * 20
# A protospacer with an in-window A (correctable by ABE) and an NGG PAM.
PROTO = "TTTAAACGTTTTTTTTTTTT"


def _resolve(ref: ReferenceGenome, zero_based: int, alt: str) -> ResolvedVariant:
    base = str(
        ref.fetch(
            GenomicInterval(chrom="chr2", start=zero_based, end=zero_based + 1, strand=Strand.PLUS)
        )
    )
    return resolve(f"chr2:{zero_based + 1}:{base}>{alt}", reference=ref)


def _abe_ref(make_reference: MakeRef) -> ReferenceGenome:
    return make_reference({"chr2": PAD + PROTO + "TGG" + PAD})


def test_end_to_end_populated_menu(make_reference: MakeRef) -> None:
    ref = _abe_ref(make_reference)
    rv = _resolve(ref, 25, "G")  # install A->G
    menu = design(rv, reference=ref, intent=EditIntent.INSTALL)
    assert isinstance(menu, RankedMenu)
    assert menu.candidates  # at least one chemistry produced candidates
    assert isinstance(menu.provenance, Provenance)
    assert menu.pareto_front  # the front is always non-empty for a non-empty menu
    assert menu.rationale is not None and "Routing" in menu.rationale
    assert {Chemistry.BASE_ABE} & {c.chemistry for c in menu.candidates}


def test_provenance_records_reference_dataset_version(make_reference: MakeRef) -> None:
    # A menu's provenance must not under-report its inputs: when the reference
    # carries a pinned build descriptor, it is recorded in provenance.datasets.
    from alleleforge.types.provenance import DatasetVersion

    ref = _abe_ref(make_reference)
    ref.dataset_version = DatasetVersion(
        name="hg38", version="GRCh38.p14", source_url="http://x", citation="Ensembl"
    )
    rv = _resolve(ref, 25, "G")
    menu = design(rv, reference=ref, intent=EditIntent.INSTALL)
    assert menu.provenance is not None
    recorded = {(d.name, d.version) for d in menu.provenance.datasets}
    assert ("hg38", "GRCh38.p14") in recorded


def test_completeness_property(make_reference: MakeRef) -> None:
    # Every candidate has efficiency + outcome, and either an off-target report
    # or an explicit reason it lacks one (surfaced in flags).
    ref = _abe_ref(make_reference)
    rv = _resolve(ref, 25, "G")
    menu = design(rv, reference=ref, intent=EditIntent.INSTALL)
    for c in menu.candidates:
        assert c.efficiency is not None
        assert c.outcome is not None and c.outcome.alleles
        assert c.offtarget is not None or any("offtarget" in f or "pam" in f for f in c.flags)


def test_resolves_string_input(make_reference: MakeRef) -> None:
    ref = _abe_ref(make_reference)
    base = str(ref.fetch(GenomicInterval(chrom="chr2", start=25, end=26, strand=Strand.PLUS)))
    menu = design(f"chr2:26:{base}>G", reference=ref, intent=EditIntent.INSTALL)
    assert menu.candidates


def test_knock_out_routes_to_nuclease_only(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + "ACGTAACGTTACGTAACGTT" + "TGG" + PAD})
    rv = _resolve(ref, 25, "G")
    menu = design(rv, reference=ref, intent=EditIntent.KNOCK_OUT)
    assert menu.candidates
    assert {c.chemistry for c in menu.candidates} == {Chemistry.CAS9_NUCLEASE}


def test_provenance_records_the_override_scorer_not_the_default(make_reference: MakeRef) -> None:
    # Provenance must name the model that actually scored the candidates. When the
    # caller overrides the default efficiency scorer (e.g. the opt-in trained Rule
    # Set 3 model), the menu's provenance.models must record the override's card,
    # not the default ensemble it replaced — otherwise a re-run from the stamped
    # provenance reproduces different numbers.
    from alleleforge.model_zoo.registry import ModelCard
    from alleleforge.scoring.cas9_efficiency import EnsembleEfficiencyScorer

    class _OverrideScorer:
        name = "rule-set-3-override"

        def score(self, context: str) -> Prediction[float]:
            return EnsembleEfficiencyScorer().score(context)

        def model_card(self) -> ModelCard:
            return ModelCard(
                name="rule-set-3-override",
                version="9.9",
                chemistry="cas9_nuclease",
                training_data="test override",
                intended_use="test",
                out_of_scope_use="test",
                license="mit",
                citation="test",
                known_failure_modes=("test-only",),
            )

    ref = make_reference({"chr2": PAD + "ACGTAACGTTACGTAACGTT" + "TGG" + PAD})
    rv = _resolve(ref, 25, "G")
    menu = design(
        rv,
        reference=ref,
        intent=EditIntent.KNOCK_OUT,
        cas9_efficiency_scorer=_OverrideScorer(),  # type: ignore[arg-type]
    )
    assert menu.provenance is not None
    names = {m.name for m in menu.provenance.models}
    assert "rule-set-3-override" in names
    assert "cas9-efficiency-ensemble" not in names


def test_chemistries_filter_restricts(make_reference: MakeRef) -> None:
    ref = _abe_ref(make_reference)
    rv = _resolve(ref, 25, "G")
    menu = design(rv, reference=ref, intent=EditIntent.INSTALL, chemistries=[Chemistry.BASE_ABE])
    assert {c.chemistry for c in menu.candidates} <= {Chemistry.BASE_ABE}
    assert "not requested" in menu.rationale  # prime was eligible but dropped


def test_requesting_ineligible_chemistry_is_noted(make_reference: MakeRef) -> None:
    ref = _abe_ref(make_reference)
    rv = _resolve(ref, 25, "G")
    menu = design(
        rv, reference=ref, intent=EditIntent.INSTALL, chemistries=[Chemistry.CAS9_NUCLEASE]
    )
    assert "requested but not eligible" in menu.rationale
    assert not menu.candidates  # nuclease is ineligible for an install intent


def test_ineligible_chemistry_notes_are_deterministically_ordered(make_reference: MakeRef) -> None:
    # Two requested-but-ineligible chemistries for an A->G install (CBE is a C->T
    # editor; nuclease makes indels, not a precise install). Their notes must come
    # out in sorted order so the serialized menu rationale is byte-stable across
    # runs — a bare set-difference iteration would order them by the hash seed.
    ref = _abe_ref(make_reference)
    rv = _resolve(ref, 25, "G")
    menu = design(
        rv,
        reference=ref,
        intent=EditIntent.INSTALL,
        chemistries=[Chemistry.CAS9_NUCLEASE, Chemistry.BASE_CBE],
    )
    assert menu.rationale is not None
    i_cbe = menu.rationale.find("base_cbe: requested but not eligible")
    i_nuc = menu.rationale.find("cas9_nuclease: requested but not eligible")
    assert i_cbe != -1 and i_nuc != -1  # both ineligible and noted
    assert i_cbe < i_nuc  # sorted (base_cbe before cas9_nuclease), not hash-seed-ordered


def test_run_offtarget_false_skips(make_reference: MakeRef) -> None:
    ref = _abe_ref(make_reference)
    rv = _resolve(ref, 25, "G")
    menu = design(rv, reference=ref, intent=EditIntent.INSTALL, run_offtarget=False)
    assert all(c.offtarget is None for c in menu.candidates)


def test_reproducible_given_timestamp(make_reference: MakeRef) -> None:
    from datetime import UTC, datetime

    ref = _abe_ref(make_reference)
    rv = _resolve(ref, 25, "G")
    ts = datetime(2024, 5, 1, tzinfo=UTC)
    a = design(rv, reference=ref, intent=EditIntent.INSTALL, timestamp=ts)
    b = design(rv, reference=ref, intent=EditIntent.INSTALL, timestamp=ts)
    assert a.model_dump() == b.model_dump()


def test_eligible_but_empty_is_noted(make_reference: MakeRef) -> None:
    # A transition SNV with no nearby PAM: base editing is eligible by routing
    # but enumerates nothing; the menu records the reason and still returns.
    ref = make_reference({"chr2": "A" * 60})
    rv = _resolve(ref, 30, "G")
    menu = design(rv, reference=ref, intent=EditIntent.INSTALL)
    assert "no actionable candidate" in menu.rationale or not menu.candidates


def test_provenance_records_weights_and_seed(make_reference: MakeRef) -> None:
    ref = _abe_ref(make_reference)
    rv = _resolve(ref, 25, "G")
    menu = design(rv, reference=ref, intent=EditIntent.INSTALL)
    assert menu.provenance is not None
    snap = menu.provenance.config_snapshot
    assert snap["intent"] == "install"
    assert abs(snap["weights"]["efficiency"] - 0.35) < 1e-9


def test_provenance_records_invoked_models(make_reference: MakeRef) -> None:
    # An A->G install routes to base-editing + prime; provenance must record the
    # card-backed models for both verticals, deduped. The defaults are transparent
    # heuristics, so provenance records their honest *-baseline cards — never the
    # trained cards (be-dict / pridict2), which would misreport trained-only
    # training data and failure modes for numbers a heuristic produced.
    ref = _abe_ref(make_reference)
    rv = _resolve(ref, 25, "G")
    menu = design(rv, reference=ref, intent=EditIntent.INSTALL)
    recorded = {m.name for m in menu.provenance.models}
    assert {"be-dict-baseline", "pridict2-baseline"} <= recorded
    assert "be-dict" not in recorded and "pridict2" not in recorded  # not the trained cards
    assert "cas9-efficiency-ensemble" not in recorded  # nuclease not eligible here
    # Every recorded checkpoint carries its card metadata, not just a name.
    assert all(m.license and m.citation for m in menu.provenance.models)


def test_provenance_models_scope_to_eligible_chemistries(make_reference: MakeRef) -> None:
    # A knock-out routes to the nuclease vertical only, so provenance records the
    # Cas9 efficiency + outcome models and nothing from the other chemistries.
    ref = make_reference({"chr2": PAD + "ACGTAACGTTACGTAACGTT" + "TGG" + PAD})
    rv = _resolve(ref, 25, "G")
    menu = design(rv, reference=ref, intent=EditIntent.KNOCK_OUT)
    recorded = {m.name for m in menu.provenance.models}
    assert recorded == {"cas9-efficiency-ensemble", "indelphi-mh-baseline"}


def _prime_context() -> str:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")  # plus pegRNA PAM
    seq[55:58] = list("CCA")  # minus ngRNA PAM (PE3b)
    return "".join(seq)


def test_prime_path_yields_pegrna_candidates(make_reference: MakeRef) -> None:
    # An A->C transversion routes to prime only and exercises the pegRNA path
    # (and the ranker's pegRNA simplicity branches) through the designer.
    ref = make_reference({"chr2": _prime_context()})
    rv = _resolve(ref, 70, "C")
    menu = design(rv, reference=ref, intent=EditIntent.INSTALL)
    assert menu.candidates
    assert {c.chemistry for c in menu.candidates} == {Chemistry.PRIME}
    assert all(c.pegrna is not None for c in menu.candidates)
    # the ranking rationale is appended to each candidate's own note
    assert menu.candidates[0].rationale is not None
    assert "score" in menu.candidates[0].rationale


def test_chemistry_failure_degrades_gracefully(
    make_reference: MakeRef, monkeypatch: pytest.MonkeyPatch
) -> None:
    # If a chemistry's vertical raises (e.g. an unavailable model), the designer
    # records why and returns the rest of the menu rather than failing.
    import alleleforge.design.designer as designer_mod

    def _boom(*args: object, **kwargs: object) -> list[object]:
        raise RuntimeError("model checkpoint unavailable")

    monkeypatch.setattr(designer_mod, "design_cas9", _boom)
    ref = make_reference({"chr2": PAD + "ACGTAACGTTACGTAACGTT" + "TGG" + PAD})
    rv = _resolve(ref, 25, "G")
    menu = design(rv, reference=ref, intent=EditIntent.KNOCK_OUT)
    assert not menu.candidates
    assert "skipped" in menu.rationale
    assert "model checkpoint unavailable" in menu.rationale


def test_unexpected_defect_is_distinguished_from_no_design(
    make_reference: MakeRef, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An unexpected exception type (a code defect) must not be swallowed as a
    # benign "skipped" / "no design"; it is surfaced as an ERROR note instead.
    import alleleforge.design.designer as designer_mod

    def _defect(*args: object, **kwargs: object) -> list[object]:
        raise AttributeError("'NoneType' object has no attribute 'foo'")

    monkeypatch.setattr(designer_mod, "design_cas9", _defect)
    ref = make_reference({"chr2": PAD + "ACGTAACGTTACGTAACGTT" + "TGG" + PAD})
    rv = _resolve(ref, 25, "G")
    menu = design(rv, reference=ref, intent=EditIntent.KNOCK_OUT)
    assert menu.rationale is not None
    assert "ERROR" in menu.rationale and "unexpected AttributeError" in menu.rationale
    assert "skipped (AttributeError" not in menu.rationale  # not masked as graceful


def test_provenance_snapshots_the_resolved_settings(make_reference: MakeRef) -> None:
    # config_snapshot records the full resolved settings that governed the run
    # (minus the volatile cache_dir), not just a hand-built subset that can drift.
    from alleleforge.config import Settings

    ref = _abe_ref(make_reference)
    rv = _resolve(ref, 25, "G")
    settings = Settings(seed=4242, maf_threshold=0.02)
    menu = design(rv, reference=ref, intent=EditIntent.INSTALL, settings=settings)
    assert menu.provenance is not None
    snap = menu.provenance.config_snapshot["settings"]
    assert snap["seed"] == 4242
    assert abs(snap["maf_threshold"] - 0.02) < 1e-9
    assert "cache_dir" not in snap  # volatile per-machine path is excluded


def _prime_ref(make_reference: MakeRef) -> ReferenceGenome:
    """A locus that yields pegRNA candidates for chr2:71:A>C."""
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")  # plus pegRNA PAM
    seq[55:58] = list("CCA")  # minus ngRNA PAM (PE3b)
    return make_reference({"chr2": "".join(seq)})


def test_prime_provenance_records_both_default_models(make_reference: MakeRef) -> None:
    """The flagship's outcome model must appear in provenance like its siblings.

    `p_intended` from the byproduct predictor feeds the menu's cleanliness
    objective, so a provenance block naming only the efficiency scorer under-reports
    which models produced the numbers being ranked. The nuclease and base-editor
    verticals each record both of theirs.
    """
    menu = design(
        "chr2:71:A>C",
        reference=_prime_ref(make_reference),
        intent=EditIntent.INSTALL,
        run_offtarget=False,
    )
    assert menu.provenance is not None
    names = {m.name for m in menu.provenance.models}
    assert {"pridict2-baseline", "prime-outcome-baseline"} <= names


def test_a_prime_override_is_the_model_recorded(make_reference: MakeRef) -> None:
    """Provenance must name the model that scored, not the default it replaced.

    Otherwise a re-run from the stamped provenance reproduces different numbers —
    the exact failure the nuclease and base-editor verticals already guard against.
    """

    class _Override:
        name = "stand-in-prime-scorer"

        def model_card(self) -> ModelCard:
            return default_registry().get("pridict2")  # the trained card

        def score(
            self,
            pegrna: PegRNA,
            *,
            cell_context: str | None = None,
            chromatin: object | None = None,
        ) -> Prediction[float]:
            return Prediction[float](
                value=0.42,
                interval=(0.3, 0.5),
                interval_level=0.8,
                method=UncertaintyMethod.HEURISTIC,
            )

    menu = design(
        "chr2:71:A>C",
        reference=_prime_ref(make_reference),
        intent=EditIntent.INSTALL,
        run_offtarget=False,
        prime_efficiency_scorer=_Override(),  # type: ignore[arg-type]
    )
    assert menu.provenance is not None
    names = {m.name for m in menu.provenance.models}
    assert "pridict2" in names, "the override's card must be recorded"
    assert "pridict2-baseline" not in names, "the replaced default must not be"
    assert menu.best is not None and menu.best.efficiency is not None
    assert menu.best.efficiency.value == pytest.approx(0.42)


def test_no_shipped_trained_prime_scorer_satisfies_the_override_protocol() -> None:
    """Pins the R1 gap so a future session does not rediscover it as a surprise.

    `design()` accepts a prime-efficiency override, but nothing trained can be
    passed to it today: the real PRIDICT2.0 path is a *sequence-level* `design()`
    API rather than a `score(pegrna, ...)` one, and the two cross-check adapters
    implement the protocol only to refuse. This test fails the moment a genuine
    trained per-pegRNA scorer lands — which is the point, since the docstrings that
    say "no trained scorer today" will need updating with it.
    """
    from alleleforge.scoring.pridict_engine import PridictEngineAdapter
    from alleleforge.scoring.prime_efficiency import DeepPrimeAdapter, GenETAdapter

    assert not hasattr(PridictEngineAdapter, "score"), (
        "PridictEngineAdapter is sequence-level; if it grew score(), wire it into design()"
    )
    for placeholder in (DeepPrimeAdapter, GenETAdapter):
        doc = placeholder.score.__doc__ or ""
        assert "refuse" in doc or "placeholder" in doc, (
            f"{placeholder.__name__} looks like a real scorer now; wire it and update the docs"
        )


def test_provenance_names_every_data_source_a_run_consumed(make_reference: MakeRef) -> None:
    """A population/haplotype-aware result must say *which* data made it so.

    `_collect_datasets` recorded only the reference, gnomAD and ClinVar, and only
    when they carried a descriptor. A haplotype panel was never collected at all,
    so a run could be haplotype-aware and record nothing about it — leaving a
    reader unable to tell an unpopulated scan from a populated one, and the result
    not re-derivable from its own provenance.
    """
    from alleleforge.data.gnomad import GnomadDB
    from alleleforge.data.haplotypes import HaplotypePanel
    from alleleforge.types.provenance import DatasetVersion

    reference = _prime_ref(make_reference)
    gnomad = GnomadDB([])
    gnomad.dataset_version = DatasetVersion(name="gnomad-sites", version="sha256:aaa")  # type: ignore[attr-defined]
    panel = HaplotypePanel([], source="panel")
    panel.dataset_version = DatasetVersion(name="haplotype-panel", version="sha256:bbb")  # type: ignore[attr-defined]

    menu = design(
        "chr2:71:A>C",
        reference=reference,
        intent=EditIntent.INSTALL,
        run_offtarget=False,
        gnomad=gnomad,
        haplotypes=panel,
    )
    assert menu.provenance is not None
    recorded = {(d.name, d.version) for d in menu.provenance.datasets}
    assert ("gnomad-sites", "sha256:aaa") in recorded
    assert ("haplotype-panel", "sha256:bbb") in recorded


def test_an_undescribed_source_is_simply_absent(make_reference: MakeRef) -> None:
    """A source with no descriptor must not invent one — silence beats a guess."""
    from alleleforge.data.gnomad import GnomadDB

    menu = design(
        "chr2:71:A>C",
        reference=_prime_ref(make_reference),
        intent=EditIntent.INSTALL,
        run_offtarget=False,
        gnomad=GnomadDB([]),
    )
    assert menu.provenance is not None
    assert not any(d.name == "gnomad-sites" for d in menu.provenance.datasets)


def test_a_restricted_scan_is_distinguishable_from_a_genome_wide_one(
    make_reference: MakeRef,
) -> None:
    """ "0 off-targets" must not read the same for a whole genome and a 100 bp window.

    A restricted scan reports far fewer sites than a genome-wide one, and without a
    record of the restriction the two results are identical to a reader — the
    reassuring value again, on the safety axis.
    """
    reference = _prime_ref(make_reference)
    wide = design(
        "chr2:71:A>C", reference=reference, intent=EditIntent.INSTALL, run_offtarget=False
    )
    assert wide.provenance is not None
    assert wide.provenance.config_snapshot["offtarget_regions"] is None  # whole genome

    narrow = design(
        "chr2:71:A>C",
        reference=reference,
        intent=EditIntent.INSTALL,
        run_offtarget=False,
        offtarget_regions=[GenomicInterval(chrom="chr2", start=0, end=140, strand=Strand.PLUS)],
    )
    assert narrow.provenance is not None
    snapshot = narrow.provenance.config_snapshot["offtarget_regions"]
    assert snapshot == {"n": 1, "bases": 140, "sha256": snapshot["sha256"]}
    assert snapshot["sha256"]


def test_the_region_pin_is_order_independent_but_content_sensitive(
    make_reference: MakeRef,
) -> None:
    """Two runs agree iff they restricted to the same intervals, however ordered."""
    reference = _prime_ref(make_reference)
    a = GenomicInterval(chrom="chr2", start=0, end=50, strand=Strand.PLUS)
    b = GenomicInterval(chrom="chr2", start=60, end=90, strand=Strand.PLUS)

    def _pin(regions: list[GenomicInterval]) -> str:
        menu = design(
            "chr2:71:A>C",
            reference=reference,
            intent=EditIntent.INSTALL,
            run_offtarget=False,
            offtarget_regions=regions,
        )
        assert menu.provenance is not None
        return str(menu.provenance.config_snapshot["offtarget_regions"]["sha256"])

    assert _pin([a, b]) == _pin([b, a])
    assert _pin([a, b]) != _pin([a])


def _clinvar_stub(
    significance: ClinicalSignificance,
    *,
    review_status: str = "criteria provided, single submitter",
) -> object:
    """A ClinVar database returning one record with the given classification."""
    from alleleforge.data.clinvar import ClinVarRecord

    record = ClinVarRecord(
        accession=ClinVarAccession(value="VCV000000123"),
        variant=Variant(chrom="chr2", pos=24, ref="T", alt="A", build="hg38"),
        significance=significance,
        review_status=review_status,
        raw_significance=significance.value.title(),
    )

    class _DB:
        def get(self, accession: object) -> ClinVarRecord:
            return record

    return _DB()


@pytest.mark.parametrize(
    ("significance", "intent", "expected"),
    [
        (ClinicalSignificance.BENIGN, EditIntent.CORRECT, "confirm the target is the allele"),
        (
            ClinicalSignificance.LIKELY_BENIGN,
            EditIntent.CORRECT,
            "confirm the target is the allele",
        ),
        (ClinicalSignificance.UNCERTAIN, EditIntent.CORRECT, "clinical benefit is not asserted"),
        (ClinicalSignificance.PATHOGENIC, EditIntent.INSTALL, "a disease model, not a correction"),
    ],
)
def test_the_clinvar_classification_reaches_the_menu(
    make_reference: MakeRef,
    significance: ClinicalSignificance,
    intent: EditIntent,
    expected: str,
) -> None:
    """Resolving an accession kept the coordinates and threw away the reason.

    A ClinVar accession is chosen for its classification. `_from_clinvar` returned
    only `record.variant`, so a menu for a variant ClinVar calls Benign read exactly
    like a menu for a pathogenic one — the tool designed a "correction" for an allele
    the database says is harmless and said nothing.
    """
    ref = make_reference({"chr2": "T" * 15 + "ACGTAACGTTACGTAACGTT" + "TGG" + "T" * 15})
    menu = design(
        "VCV000000123",
        intent=intent,
        reference=ref,
        clinvar=_clinvar_stub(significance),
        run_offtarget=False,
    )
    assert menu.rationale is not None
    # The assertion itself, verbatim enough to be actionable...
    assert f"ClinVar: {significance.value.replace('_', ' ')}" in menu.rationale
    assert "criteria provided" in menu.rationale  # the review status, not just the class
    # ...and the tension between it and what the user asked for.
    assert expected in menu.rationale


def test_a_congruent_intent_gets_the_classification_but_no_warning(
    make_reference: MakeRef,
) -> None:
    """Correcting a pathogenic variant is the ordinary case and must stay quiet.

    Without this the parametrized test above passes on an implementation that
    appends a caution to every design, which would be noise rather than information.
    """
    ref = make_reference({"chr2": "T" * 15 + "ACGTAACGTTACGTAACGTT" + "TGG" + "T" * 15})
    menu = design(
        "VCV000000123",
        intent=EditIntent.CORRECT,
        reference=ref,
        clinvar=_clinvar_stub(ClinicalSignificance.PATHOGENIC),
        run_offtarget=False,
    )
    assert menu.rationale is not None
    assert "ClinVar: pathogenic" in menu.rationale
    assert "confirm the target" not in menu.rationale
    assert "disease model" not in menu.rationale
    assert "not asserted" not in menu.rationale


def _effect_stub(consequence: Consequence, **kw: object) -> object:
    """An effect predictor returning one fixed consequence."""
    effect = VariantEffect(consequence=consequence, impact=impact_of(consequence), **kw)  # type: ignore[arg-type]

    class _P:
        def predict(self, variant: object, *, transcript: str = "MANE_SELECT") -> VariantEffect:
            return effect

    return _P()


def test_the_predicted_effect_reaches_the_menu(make_reference: MakeRef) -> None:
    """A VEP lookup was computed, stored on the resolved variant, and read by nothing.

    The user pays a network round trip for it — and, since it goes to a third-party
    API, an explicit decision to disclose their variant — and got no answer anywhere
    in the output. The gene, the consequence, the impact tier and the protein change
    all sat on `ResolvedVariant.effect` unread.
    """
    ref = make_reference({"chr2": "T" * 15 + "ACGTAACGTTACGTAACGTT" + "TGG" + "T" * 15})
    menu = design(
        "chr2:25:T>A",
        intent=EditIntent.CORRECT,
        reference=ref,
        effect=_effect_stub(
            Consequence.MISSENSE,
            gene="HBB",
            transcript="ENST00000335295",
            hgvs_p="p.Glu7Val",
        ),
        run_offtarget=False,
    )
    assert menu.rationale is not None
    assert "Predicted effect: missense variant (moderate impact) in HBB" in menu.rationale
    assert "p.Glu7Val" in menu.rationale
    assert "ENST00000335295" in menu.rationale
    # A moderate-impact correction is the ordinary case and gets no caution, or the
    # caution asserted below would appear on every design and mean nothing.
    assert "confirm this is the change you mean to make" not in menu.rationale


def test_a_correction_with_no_predicted_protein_impact_is_flagged(
    make_reference: MakeRef,
) -> None:
    """Correcting a modifier-impact variant is worth a second look, not a refusal."""
    ref = make_reference({"chr2": "T" * 15 + "ACGTAACGTTACGTAACGTT" + "TGG" + "T" * 15})
    menu = design(
        "chr2:25:T>A",
        intent=EditIntent.CORRECT,
        reference=ref,
        effect=_effect_stub(Consequence.INTRON, gene="HBB"),
        run_offtarget=False,
    )
    assert menu.rationale is not None
    assert "modifier impact" in menu.rationale
    assert "confirm this is the change you mean to make" in menu.rationale
    assert menu.candidates or "no actionable candidate" in menu.rationale  # not refused


def test_a_non_canonical_transcript_says_so(make_reference: MakeRef) -> None:
    """The same variant is missense on one transcript and intronic on another."""
    ref = make_reference({"chr2": "T" * 15 + "ACGTAACGTTACGTAACGTT" + "TGG" + "T" * 15})
    menu = design(
        "chr2:25:T>A",
        intent=EditIntent.CORRECT,
        reference=ref,
        effect=_effect_stub(Consequence.MISSENSE, transcript="ENST00000000001", is_canonical=False),
        run_offtarget=False,
    )
    assert menu.rationale is not None
    assert "(not the canonical transcript)" in menu.rationale


def _prime_case() -> tuple[str, str, EditIntent]:
    contig = list("AT" * 70)
    contig[63:66] = list("TGG")
    contig[58:61] = list("CCA")
    return "".join(contig), "chr2:71:A>C", EditIntent.INSTALL


def _base_editor_case() -> tuple[str, str, EditIntent]:
    contig = list("ACGT" * 125 + "TTTTTATTTTTTTTTTTTTT" + "TGG" + "ACGT" * 125)
    return "".join(contig), "chr2:506:A>G", EditIntent.INSTALL


def _nuclease_case() -> tuple[str, str, EditIntent]:
    contig = "T" * 15 + "ACGTAACGTTACGTAACGTT" + "TGG" + "T" * 15
    return contig, "chr2:25:T>A", EditIntent.KNOCK_OUT


@pytest.mark.parametrize("run_offtarget", [False, True])
@pytest.mark.parametrize(
    "case", [_prime_case, _base_editor_case, _nuclease_case], ids=["prime", "base", "nuclease"]
)
def test_every_vertical_flags_an_unsearched_off_target_axis(
    make_reference: MakeRef,
    run_offtarget: bool,
    case: Callable[[], tuple[str, str, EditIntent]],
) -> None:
    """All three verticals, or the honesty depends on which chemistry you routed to.

    `_safety` returns a full 1.0 with no off-target report, so a candidate nobody
    screened carries `safe 1.00` into the composite. Each vertical has to say so
    itself — a check in one of them leaves the other two silently reassuring, which is
    how most of the gaps in this audit began.
    """
    contig, variant, intent = case()
    ref = make_reference({"chr2": contig})
    menu = design(variant, intent=intent, reference=ref, run_offtarget=run_offtarget)
    assert menu.candidates, "fixture produced no candidates"
    for candidate in menu.candidates:
        assert ("offtarget-not-searched" in candidate.flags) is (candidate.offtarget is None)
    if not run_offtarget:
        assert all("offtarget-not-searched" in c.flags for c in menu.candidates)


def test_a_one_shot_safety_input_reaches_every_chemistry(make_reference: MakeRef) -> None:
    """`design` fans out to three verticals; a generator reached only the first.

    `haplotypes` and `patient_vcf` are typed `Iterable`, and `design` hands each of
    them to every eligible chemistry in turn. A caller passing a generator had it
    consumed by whichever ran first, so one menu could hold haplotype-aware
    base-editor candidates beside reference-only pegRNAs — screened differently,
    presented identically, and ranked against each other on a safety axis they did not
    share.
    """
    # A pseudo-random contig, seeded here so it is deterministic: a repeating one gives
    # the base editor a window but leaves prime with no PAM, and the whole point is a
    # menu holding two chemistries.
    rng = random.Random(3)
    bases = [rng.choice("ACGT") for _ in range(2000)]
    bases[500:520] = list("TTTTTATTTTTTTTTTTTTT")
    bases[520:523] = list("TGG")
    sequence = "".join(bases)
    ref = make_reference({"chr2": sequence})
    panel = [
        Haplotype(
            hap_id="H1",
            interval=GenomicInterval(chrom="chr2", start=480, end=560, strand=Strand.PLUS),
            variants=(Variant(chrom="chr2", pos=510, ref=sequence[510], alt="C"),),
            frequencies={"afr": 0.2},
            source="1000g",
        )
    ]
    patient = [Variant(chrom="chr2", pos=511, ref=sequence[511], alt="G", build="hg38")]

    def _seen(
        haplotypes: object, patient_vcf: object
    ) -> dict[str, set[tuple[int | None, int | None]]]:
        menu = design(
            "chr2:506:A>G",
            intent=EditIntent.INSTALL,
            reference=ref,
            haplotypes=haplotypes,  # type: ignore[arg-type]
            patient_vcf=patient_vcf,  # type: ignore[arg-type]
            populations=("afr",),
        )
        out: dict[str, set[tuple[int | None, int | None]]] = {}
        for candidate in menu.candidates:
            if candidate.offtarget is not None:
                considered = candidate.offtarget.sources_considered
                out.setdefault(candidate.chemistry.value, set()).add(
                    (considered.get("haplotypes"), considered.get("patient-vcf"))
                )
        return out

    from_lists = _seen(list(panel), list(patient))
    assert len(from_lists) > 1, "fixture routed to one chemistry — the check would be vacuous"

    # The point: a one-shot iterable produces the same per-chemistry picture.
    assert _seen(iter(panel), iter(patient)) == from_lists
    # ...and every chemistry actually saw both sources, rather than all seeing neither.
    assert all(seen == {(1, 1)} for seen in from_lists.values()), from_lists


def test_an_empty_prime_vertical_explains_itself_in_the_menu(
    make_reference: MakeRef,
) -> None:
    """The rationale said "eligible but no actionable candidate enumerated" and stopped.

    Prime is the flagship chemistry and the one most often eligible-but-empty, and the
    reasons have different remedies — the other strand, a different PAM, another
    chemistry, or a genuine dead end. Naming none of them leaves a scientist with a
    result they cannot act on and cannot distinguish from a bug.
    """
    ref = _abe_ref(make_reference)
    menu = design("chr2:26:A>G", reference=ref, intent=EditIntent.INSTALL)

    assert menu.rationale is not None
    prime_note = next(
        (line for line in menu.rationale.splitlines() if line.strip().startswith("- prime:")),
        None,
    )
    assert prime_note is not None, f"no prime note in the rationale: {menu.rationale}"
    if "no actionable candidate" in prime_note:
        assert " — " in prime_note, f"empty prime vertical gave no reason: {prime_note}"
        # The reason is one of the documented ones, with its count.
        from alleleforge.enumerate.prime import REJECTION_REASONS

        assert any(text in prime_note for text in REJECTION_REASONS.values())
