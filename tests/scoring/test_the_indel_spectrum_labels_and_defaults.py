"""The exact alleles the MMEJ baseline emits, and the defaults its callers rely on.

The microhomology length is not an internal: it is printed in the allele label a user
reads (`del8:mh3@4`) and it drives the weight. Every existing fixture was a repeat-rich
context whose alleles were only ever inspected in aggregate, so the counter could start at
1, advance by 2, or demand 2 bp of homology, and nothing failed — every deletion simply
shifted together, which an ordering assertion cannot see.

This file uses a context small enough to enumerate by hand. ``ACGTACGT`` cut at 4 has one
microhomology per offset and no others: `ACGT` repeats once, so i=0 matches 4 bases, i=1
matches 3, i=2 matches 2, i=3 matches 1, and every mismatched (i, j) pair contributes
nothing. The whole allele set is therefore fixed, and the labels pin the counter exactly
rather than relative to itself.

The magnitudes behind the shape (the exponential's 8.0, the 0.5 per homology base, the
A/T-over-G/C insertion bias, the 5% byproduct floor) are an unspecified heuristic with no
published source, so they are deliberately not frozen here: a 10% order-preserving shift
in any of them is an accepted survivor, and the properties that are documented are pinned
in `test_the_indel_spectrums_documented_shape.py` instead.
"""

from __future__ import annotations

import inspect
import math

import pytest

from alleleforge.scoring.cas9_outcome import (
    DEFAULT_MAX_DELETION,
    InDelphiAdapter,
    LindelAdapter,
    MicrohomologyOutcomePredictor,
    XCrispAdapter,
    _lindel_outcome,
    ensemble_outcome,
)
from alleleforge.types.edit import AlleleOutcome, EditOutcome

#: One `ACGT` repeat either side of the cut: every microhomology is hand-countable.
_EXACT = "ACGTACGT"
_EXACT_CUT = 4


def _alleles(ctx: str, cut: int, **kw: object) -> list[str]:
    outcome = MicrohomologyOutcomePredictor().predict(ctx, cut, **kw)  # type: ignore[arg-type]
    return sorted(a.allele for a in outcome.alleles)


def test_the_emitted_allele_set_is_exactly_what_the_mechanism_implies() -> None:
    assert _alleles(_EXACT, _EXACT_CUT) == sorted(
        [
            "del4:mh4@0",  # ACGT|ACGT: all four bases match across the cut
            "del4:mh3@1",  # CGT matches, then the 3' copy runs out
            "del4:mh2@2",
            "del4:mh1@3",  # a single-base microhomology is still a microhomology
            "ins1:T",  # templated by the -1 base
            "ins1:A",  # templated by the +1 base
            "other",  # the unmodelled-byproduct floor
        ]
    )


def test_a_one_base_microhomology_is_not_discarded() -> None:
    """The `m < 1` filter rejects *no* homology, not short homology."""
    assert "del4:mh1@3" in _alleles(_EXACT, _EXACT_CUT)


def test_the_insertion_templated_by_the_minus_one_base_appears_at_cut_one() -> None:
    """`cut >= 1` is the condition, and 1 satisfies it: two insertions, not one.

    Counting rather than naming, because at cut 0 the +1 branch emits the same label
    the -1 branch would have: `ins1:A` is present either way and says nothing.
    """
    at_one = [a for a in _alleles("ACGT", 1) if a.startswith("ins1")]
    assert sorted(at_one) == ["ins1:A", "ins1:C"], "the -1 base (A) and the +1 base (C)"
    at_zero = [a for a in _alleles("ACGT", 0) if a.startswith("ins1")]
    assert at_zero == ["ins1:A"], "nothing is 5' of base 0 to template an insertion"


def test_marking_frameshifts_is_off_by_default() -> None:
    """A plain predict must claim nothing is intended: only a knock-out asks for that."""
    assert MicrohomologyOutcomePredictor().predict(_EXACT, _EXACT_CUT).p_intended == 0.0


def test_the_byproduct_floor_is_never_an_intended_knockout_allele() -> None:
    """With marking ON — without it every allele is unintended and this measures nothing."""
    outcome = MicrohomologyOutcomePredictor().predict(_EXACT, _EXACT_CUT, mark_frameshift=True)
    other = next(a for a in outcome.alleles if a.allele == "other")
    assert not other.is_intended, (
        "'other' stands for unenumerated byproducts of unknown frame; it cannot be "
        "credited to a knock-out"
    )
    assert any(a.is_intended for a in outcome.alleles), "marking must be on for this fixture"


def test_the_deletion_limit_is_twenty_base_pairs() -> None:
    """Written out, not read from the constant: a self-derived fixture pins nothing."""
    assert DEFAULT_MAX_DELETION == 20


def test_a_deletion_of_exactly_twenty_is_modelled_and_twenty_one_is_not() -> None:
    def longest(gap: int) -> int:
        unit = "ACGT"
        ctx = "T" * 12 + unit + "G" * (gap - len(unit)) + unit + "T" * 12
        outcome = MicrohomologyOutcomePredictor().predict(ctx, 12 + len(unit))
        return max(
            (
                int(a.allele.split(":")[0].removeprefix("del"))
                for a in outcome.alleles
                if a.allele.startswith("del")
            ),
            default=0,
        )

    assert longest(20) == 20, "a 20-bp MMEJ deletion is inside the modelled range"
    assert longest(21) < 21, "a 21-bp MMEJ deletion is past the limit and must be dropped"


# --- the ensemble and the trained-model mapping -------------------------------------


def test_an_ensemble_reports_a_complete_distribution() -> None:
    one = EditOutcome(alleles=(AlleleOutcome(allele="del3", probability=1.0),))
    merged, agreement = ensemble_outcome([one, one])
    assert merged.partial is False
    assert math.isclose(sum(a.probability for a in merged.alleles), 1.0, abs_tol=1e-9)
    assert agreement == 1.0


@pytest.mark.parametrize(
    ("fraction", "intended"),
    [(0.5, True), (0.49, False)],
    ids=["on-the-threshold", "just-below"],
)
def test_a_lindel_class_is_frameshifting_from_exactly_half(fraction: float, intended: bool) -> None:
    """Both sides of the 0.5 cut-off; every prior fixture used only 1.0 and 0.0."""
    out = _lindel_outcome([0.6, 0.4], ["a", "b"], [fraction, 0.0], mark_frameshift=True, top_k=8)
    assert next(a for a in out.alleles if a.allele == "a").is_intended is intended


def test_a_lindel_tail_is_bucketed_at_exactly_half_too() -> None:
    out = _lindel_outcome(
        [0.7, 0.2, 0.1], ["a", "b", "c"], [0.0, 0.5, 0.49], mark_frameshift=True, top_k=1
    )
    buckets = {a.allele: a.probability for a in out.alleles}
    assert buckets["other_frameshift"] == pytest.approx(0.2), "0.5 belongs to the frameshifts"
    assert buckets["other_inframe"] == pytest.approx(0.1), "0.49 does not"


def test_a_lindel_in_frame_tail_is_never_intended() -> None:
    out = _lindel_outcome(
        [0.5, 0.3, 0.2], ["a", "b", "c"], [1.0, 0.0, 0.0], mark_frameshift=True, top_k=1
    )
    in_frame = next(a for a in out.alleles if a.allele == "other_inframe")
    assert in_frame.is_intended is False, (
        "the in-frame tail is the mass that does NOT knock the gene out"
    )


def test_the_lindel_mapping_reports_a_complete_distribution() -> None:
    out = _lindel_outcome([0.6, 0.4], ["a", "b"], [1.0, 0.0], mark_frameshift=True, top_k=8)
    assert out.partial is False, (
        "the mapping normalizes over the kept classes plus both tail buckets, so it "
        "covers the whole space Lindel reported"
    )
    assert math.isclose(sum(a.probability for a in out.alleles), 1.0, abs_tol=1e-9)


@pytest.mark.parametrize(
    "predictor",
    [MicrohomologyOutcomePredictor, InDelphiAdapter, LindelAdapter, XCrispAdapter],
    ids=lambda p: p.__name__,
)
def test_every_outcome_predictor_takes_the_call_the_designer_makes(
    predictor: type,
) -> None:
    """One signature, including the placeholders — a refusal must be reachable.

    `design/cas9.py` calls every outcome predictor as
    `predict(context, cut, mark_frameshift=...)`. The two license-gated placeholders
    took only `(context, cut)`, so plugging one in raised `TypeError: unexpected
    keyword argument 'mark_frameshift'` from inside the library and never reached the
    `NotImplementedError` that names LindelAdapter and the scope spec. The useful
    message existed and the product could not get to it.

    A trained adapter defaulting `mark_frameshift` to `True` would separately credit
    frameshifting byproducts as the intended edit for a *precise* design. The trained
    paths cannot run in CI, so the signature is the surface this is checkable on — and
    it is the surface a caller relies on.
    """
    params = inspect.signature(predictor.predict).parameters
    assert "mark_frameshift" in params, "the designer passes this to every predictor"
    assert params["mark_frameshift"].default is False
    assert params["max_del"].default == DEFAULT_MAX_DELETION


def test_an_unsupported_placeholder_refuses_with_the_message_it_wrote() -> None:
    """Through the designer's own calling convention, not a hand-narrowed one."""
    with pytest.raises(NotImplementedError, match="LindelAdapter"):
        InDelphiAdapter(consent=True).predict("ACGT" * 20, 40, mark_frameshift=True)


def test_a_placeholder_does_not_advertise_itself_as_the_default() -> None:
    """Its docstring called it "default outcome model"; the base class calls it a
    placeholder and the scope spec calls it out of scope. One of the three was wrong."""
    doc = InDelphiAdapter.__doc__ or ""
    assert "placeholder" in doc
    assert "MicrohomologyOutcomePredictor" in doc, "say what the real default is"


def test_the_lindel_adapter_keeps_the_documented_number_of_classes() -> None:
    """`top_k` is documented as the verbatim-kept class count; the tail is bucketed."""
    assert inspect.signature(LindelAdapter.__init__).parameters["top_k"].default == 24
