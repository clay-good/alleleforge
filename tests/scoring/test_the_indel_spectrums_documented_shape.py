"""The MMEJ baseline's documented shape, its frame rule, and its honesty floor.

`MicrohomologyOutcomePredictor` is the shipped default indel-spectrum model, and
`p_intended` over its distribution is what a knock-out candidate is ranked by. A constant
pass left most of the module alive, and the reason is one fixture: a single repeat-rich
context at a single cut, asserted only through "1-bp insertions are intended" and
"p_intended > 0".

Nothing asserted the thing that makes the number mean anything: an **in-frame** deletion
must not be counted as intended. A 3-bp deletion preserves the reading frame and knocks
nothing out, and `del_len % 3 != 0` could have become `% 4 != 0` with the suite green,
crediting a knock-out design for alleles that leave the protein intact.

The module documents its own shape in prose — longer microhomology and shorter deletions
favored (the inDelphi form), the -1 nucleotide templating the *dominant* 1-bp insertion,
an unmodeled-byproduct floor that "keeps the model honest". Those are the properties worth
pinning; the fitted magnitudes behind them are an unspecified heuristic, so this file tests
direction and order rather than freezing numbers it cannot source.
"""

from __future__ import annotations

import math

import pytest

from alleleforge.scoring.cas9_outcome import (
    DEFAULT_MAX_DELETION,
    MicrohomologyOutcomePredictor,
    _is_frameshift,
)

#: Repeat-rich, so microhomologies (and therefore deletions) exist at the cut.
_CTX = "AACGTCAACGTCAACGTCAAGGTTGGTTGGTTACGT"
_CUT = 18


def _predict(**kw: object) -> object:
    return MicrohomologyOutcomePredictor().predict(_CTX, _CUT, **kw)  # type: ignore[arg-type]


# --- the frame rule -----------------------------------------------------------------


@pytest.mark.parametrize("del_len", [3, 6, 9, 12])
def test_an_in_frame_deletion_is_not_a_frameshift(del_len: int) -> None:
    assert not _is_frameshift(f"del{del_len}:mh2@0", del_len)


@pytest.mark.parametrize("del_len", [1, 2, 4, 5, 7, 8])
def test_an_out_of_frame_deletion_is_a_frameshift(del_len: int) -> None:
    assert _is_frameshift(f"del{del_len}:mh2@0", del_len)


def test_a_one_base_insertion_is_always_a_frameshift() -> None:
    assert _is_frameshift("ins1:A", 0)


def test_a_knockout_does_not_count_in_frame_deletions_as_intended() -> None:
    """The assertion the existing fixture never made, and the reason it matters."""
    outcome = MicrohomologyOutcomePredictor().predict(_CTX, _CUT, mark_frameshift=True)
    in_frame = [a for a in outcome.alleles if a.allele.startswith("del") and _dl(a.allele) % 3 == 0]
    assert in_frame, "this context must produce an in-frame deletion, or nothing is measured"
    for allele in in_frame:
        assert not allele.is_intended, (
            f"{allele.allele} preserves the reading frame and knocks nothing out, but is "
            "counted toward p_intended for a knock-out design"
        )
    out_of_frame = [
        a for a in outcome.alleles if a.allele.startswith("del") and _dl(a.allele) % 3 != 0
    ]
    assert out_of_frame and all(a.is_intended for a in out_of_frame)


def _dl(allele: str) -> int:
    """Return the deletion length encoded in a ``del<N>:mh...`` allele label."""
    return int(allele.split(":")[0].removeprefix("del"))


# --- the cut boundary ---------------------------------------------------------------


@pytest.mark.parametrize("cut", [0, len(_CTX)])
def test_a_cut_on_either_end_of_the_context_is_accepted(cut: int) -> None:
    """The contract is ``0 <= cut <= len(context)``; both ends are inside it."""
    outcome = MicrohomologyOutcomePredictor().predict(_CTX, cut)
    assert outcome.alleles


def test_a_cut_one_past_the_context_is_refused() -> None:
    with pytest.raises(ValueError, match="outside context"):
        MicrohomologyOutcomePredictor().predict(_CTX, len(_CTX) + 1)


# --- the documented shape -----------------------------------------------------------


def test_longer_microhomology_is_favoured_at_the_same_deletion_length() -> None:
    outcome = MicrohomologyOutcomePredictor().predict(_CTX, _CUT)
    by_len: dict[int, list[tuple[int, float]]] = {}
    for a in outcome.alleles:
        if not a.allele.startswith("del"):
            continue
        mh = int(a.allele.split(":mh")[1].split("@")[0])
        by_len.setdefault(_dl(a.allele), []).append((mh, a.probability))
    comparable = [v for v in by_len.values() if len({mh for mh, _p in v}) > 1]
    assert comparable, "no two deletions of equal length differ in microhomology here"
    for group in comparable:
        ranked = sorted(group)
        assert [p for _mh, p in ranked] == sorted(p for _mh, p in ranked), (
            "a longer microhomology must not be given less weight at equal deletion length"
        )


def test_a_shorter_deletion_is_favoured_at_the_same_microhomology() -> None:
    outcome = MicrohomologyOutcomePredictor().predict(_CTX, _CUT)
    by_mh: dict[int, list[tuple[int, float]]] = {}
    for a in outcome.alleles:
        if not a.allele.startswith("del"):
            continue
        mh = int(a.allele.split(":mh")[1].split("@")[0])
        by_mh.setdefault(mh, []).append((_dl(a.allele), a.probability))
    comparable = [v for v in by_mh.values() if len({dl for dl, _p in v}) > 1]
    assert comparable, "no two deletions of equal microhomology differ in length here"
    for group in comparable:
        ranked = sorted(group)
        assert [p for _dl_, p in ranked] == sorted((p for _dl_, p in ranked), reverse=True), (
            "a longer deletion must not be given more weight at equal microhomology"
        )


def test_the_minus_one_nucleotide_templates_the_dominant_insertion() -> None:
    """Documented as dominant: the base 5' of the cut outweighs the base 3' of it."""
    ctx, cut = "AAAAAAAAGGGGGGGG", 8  # -1 is A, +1 is G, so the two labels differ
    outcome = MicrohomologyOutcomePredictor().predict(ctx, cut)
    mass = {a.allele: a.probability for a in outcome.alleles}
    assert mass["ins1:A"] > mass["ins1:G"]


def test_an_a_or_t_templated_insertion_outweighs_a_g_or_c_one() -> None:
    def ins_mass(minus_one: str) -> float:
        ctx = "C" * 7 + minus_one + "C" * 8
        outcome = MicrohomologyOutcomePredictor().predict(ctx, 8)
        return next(a.probability for a in outcome.alleles if a.allele == f"ins1:{minus_one}")

    assert ins_mass("A") > ins_mass("G")
    assert ins_mass("T") > ins_mass("G")


def test_a_deletion_at_the_default_limit_is_modelled_and_one_past_it_is_not() -> None:
    """Both sides of `DEFAULT_MAX_DELETION`, which no fixture had ever reached."""
    # A microhomology repeated exactly DEFAULT_MAX_DELETION apart: the MMEJ deletion
    # joining the two copies is exactly the limit, so it must be kept.
    unit = "ACGT"
    spacer = "G" * (DEFAULT_MAX_DELETION - len(unit))
    ctx = "T" * 10 + unit + spacer + unit + "T" * 10
    cut = 10 + len(unit)
    lengths = {
        _dl(a.allele)
        for a in MicrohomologyOutcomePredictor().predict(ctx, cut).alleles
        if a.allele.startswith("del")
    }
    assert lengths, "fixture produced no deletion at all"
    assert DEFAULT_MAX_DELETION in lengths, "a deletion exactly at the limit was dropped"
    assert max(lengths) == DEFAULT_MAX_DELETION, f"a deletion past the limit survived: {lengths}"


# --- the honesty floor --------------------------------------------------------------


def test_the_baseline_reports_a_complete_distribution() -> None:
    outcome = MicrohomologyOutcomePredictor().predict(_CTX, _CUT)
    assert outcome.partial is False, (
        "the MMEJ baseline normalizes over its own allele set plus an explicit "
        "byproduct floor, so it covers the space it claims to"
    )
    assert math.isclose(sum(a.probability for a in outcome.alleles), 1.0, abs_tol=1e-9)


def test_the_unmodelled_byproduct_floor_is_present_and_is_a_minority() -> None:
    outcome = MicrohomologyOutcomePredictor().predict(_CTX, _CUT)
    other = next(a for a in outcome.alleles if a.allele == "other")
    assert 0.0 < other.probability < 0.5, (
        "the floor stands for unenumerated byproducts; it must exist and must not "
        "dominate a context with real microhomologies"
    )
    assert not other.is_intended


def test_a_context_with_nothing_to_model_is_all_byproduct() -> None:
    """The floor's fallback: no modelled allele at all still yields a valid distribution."""
    outcome = MicrohomologyOutcomePredictor().predict("", 0)
    assert [a.allele for a in outcome.alleles] == ["other"]
    assert outcome.alleles[0].probability == pytest.approx(1.0)
