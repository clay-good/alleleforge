"""End-to-end tests for the base-editing design vertical."""

from __future__ import annotations

from collections.abc import Callable

from alleleforge.design.base_editor import design_base_editor
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.candidate import DesignCandidate
from alleleforge.types.edit import Chemistry, EditIntent
from alleleforge.types.offtarget import OffTargetReport
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.variant.resolver import ResolvedVariant, resolve

MakeRef = Callable[[dict[str, str]], ReferenceGenome]
PAD = "T" * 20


def _resolve(ref: ReferenceGenome, zero_based: int, alt: str) -> ResolvedVariant:
    base = str(
        ref.fetch(
            GenomicInterval(chrom="chr2", start=zero_based, end=zero_based + 1, strand=Strand.PLUS)
        )
    )
    return resolve(f"chr2:{zero_based + 1}:{base}>{alt}", reference=ref)


def _abe_case(make_reference: MakeRef) -> tuple[ReferenceGenome, ResolvedVariant]:
    # A missense A->G correctable by ABE, with a bystander A in the window.
    proto = "TTTAAACGTTTTTTTTTTTT"
    ref = make_reference({"chr2": PAD + proto + "TGG" + PAD})
    return ref, _resolve(ref, 25, "G")  # INSTALL A->G at the target A (position 6)


def test_end_to_end_yields_ranked_candidates(make_reference: MakeRef) -> None:
    ref, rv = _abe_case(make_reference)
    candidates = design_base_editor(rv, EditIntent.INSTALL, reference=ref)
    assert candidates
    top = candidates[0]
    assert top.chemistry is Chemistry.BASE_ABE
    assert top.base_edit_window is not None
    assert "recommended" in top.flags


def test_every_candidate_has_outcome_and_offtarget(make_reference: MakeRef) -> None:
    ref, rv = _abe_case(make_reference)
    for c in design_base_editor(rv, EditIntent.INSTALL, reference=ref):
        assert c.efficiency is not None  # target-editing activity (P target edited)
        assert c.outcome is not None and c.outcome.alleles
        assert isinstance(c.offtarget, OffTargetReport)


def test_efficiency_axis_is_distinct_from_cleanliness(make_reference: MakeRef) -> None:
    # The efficiency axis is the raw target-editing *activity* (P target edited,
    # bystander-independent); cleanliness is the intended-allele probability mass
    # (outcome.p_intended, reduced by bystander edits). On a candidate that carries
    # bystanders the two must genuinely diverge — a regression that reconflates
    # efficiency with the clean-edit probability (the pre-fix behavior) would make
    # them equal and double-charge bystanders, yet leave the rest of the suite green.
    ref, rv = _abe_case(make_reference)
    top = design_base_editor(rv, EditIntent.INSTALL, reference=ref)[0]
    assert any(f.startswith("bystander-") for f in top.flags)  # the case has bystanders
    assert top.efficiency is not None and top.outcome is not None
    activity = top.efficiency.value
    cleanliness = float(top.outcome.p_intended)
    assert activity > cleanliness, (activity, cleanliness)  # distinct, not the same number


def test_bystander_tradeoff_surfaced(make_reference: MakeRef) -> None:
    ref, rv = _abe_case(make_reference)
    top = design_base_editor(rv, EditIntent.INSTALL, reference=ref)[0]
    assert any(f.startswith("bystander-") for f in top.flags)
    assert top.rationale is not None and "bystander" in top.rationale


def test_bystander_burden_persisted_as_calibrated_prediction(make_reference: MakeRef) -> None:
    # SPEC §8: bystander_burden is a calibrated Prediction and must survive on the
    # candidate (structured), not only in the human-readable flags/rationale.
    ref, rv = _abe_case(make_reference)
    for c in design_base_editor(rv, EditIntent.INSTALL, reference=ref):
        assert c.bystander_burden is not None
        assert c.bystander_burden.value >= 0.0
        assert (
            c.bystander_burden.interval[0]
            <= c.bystander_burden.value
            <= c.bystander_burden.interval[1]
        )


def test_ranked_by_exact_intended(make_reference: MakeRef) -> None:
    ref, rv = _abe_case(make_reference)
    cands = design_base_editor(rv, EditIntent.INSTALL, reference=ref)
    effs = [c.efficiency.value for c in cands if c.efficiency]
    assert effs == sorted(effs, reverse=True)


def test_run_offtarget_false(make_reference: MakeRef) -> None:
    ref, rv = _abe_case(make_reference)
    for c in design_base_editor(rv, EditIntent.INSTALL, reference=ref, run_offtarget=False):
        assert c.offtarget is None


def test_non_editable_variant_empty(make_reference: MakeRef) -> None:
    proto = "TTTAAACGTTTTTTTTTTTT"
    ref = make_reference({"chr2": PAD + proto + "TGG" + PAD})
    rv = _resolve(ref, 25, "C")  # A->C transversion: not base-editable
    assert design_base_editor(rv, EditIntent.INSTALL, reference=ref) == []


def test_candidates_are_design_candidates(make_reference: MakeRef) -> None:
    ref, rv = _abe_case(make_reference)
    cands = design_base_editor(rv, EditIntent.INSTALL, reference=ref, max_candidates=1)
    assert len(cands) == 1
    assert isinstance(cands[0], DesignCandidate)
    assert cands[0].has_reagent
