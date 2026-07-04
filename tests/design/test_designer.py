"""End-to-end tests for the Phase 10 designer orchestrator."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.candidate import RankedMenu
from alleleforge.types.edit import Chemistry, EditIntent
from alleleforge.types.provenance import Provenance
from alleleforge.types.sequence import GenomicInterval, Strand
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
    # card-backed models for both verticals (BE-DICT, PRIDICT2.0), deduped.
    ref = _abe_ref(make_reference)
    rv = _resolve(ref, 25, "G")
    menu = design(rv, reference=ref, intent=EditIntent.INSTALL)
    recorded = {m.name for m in menu.provenance.models}
    assert {"be-dict", "pridict2"} <= recorded
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
    assert recorded == {"cas9-efficiency-ensemble", "indelphi"}


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
