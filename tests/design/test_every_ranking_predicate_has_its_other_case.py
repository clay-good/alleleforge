"""The ranker's predicates, each measured on the case it was not written for.

Mutation testing over `design/ranking.py` killed 54 of 60 mutants. The 6 survivors were
not in the composite arithmetic — R576 pinned that — but in the *simplicity* axis, the
Pareto strictness, and the rationale that explains the ordering.

One was a live defect rather than a missing test. `_safety` chooses **per candidate**
between the worst-affected ancestry and the global worst nominated site, and both places
that explain the choice asked `any(...)`: so a menu with one ancestry-annotated candidate
and one without was described as "the safety term uses the worst-affected ancestry", full
stop, for candidates whose safety came from the worst site. gnomAD coverage is per locus,
so a mixed menu is the ordinary case. The two all-or-nothing halves were each stated
carefully; the middle was missing, and it is the half where a reader comparing two safety
scores in one menu is comparing numbers on different bases.

The rest are the R579 shape — a predicate whose other case nothing asserted. The
`nicking_guide is not None` simplicity penalty had no test that it lands on the PE3
reagent rather than the PE2 one; `_dominates` had none that domination is strict, so a
tie could dominate; and the cross-chemistry note had none that it stays off a
single-chemistry menu, which the code's own comment calls for ("a note that always
appears is not a note").
"""

from __future__ import annotations

import re

import pytest

from alleleforge.design.ranking import (
    CROSS_CHEMISTRY_NOTE,
    DEFAULT_WEIGHTS,
    indistinguishable_leaders,
    pareto_front,
    rank_candidates,
    score_candidate,
)
from alleleforge.types.candidate import DesignCandidate
from alleleforge.types.edit import Chemistry
from alleleforge.types.guide import NickingGuide, PegRNA, Spacer
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand

from .test_ranking import _cand, _score

#: All weight on efficiency, so the tolerance equals the composite spread exactly.
_ALL_EFFICIENCY = {"efficiency": 1.0, "cleanliness": 0.0, "safety": 0.0, "simplicity": 0.0}

_SAFETY = re.compile(r"(the safety term uses [^;.]*|where it was searched it uses [^;.]*)")


def _safety_sentence(candidates: list[DesignCandidate]) -> str:
    match = _SAFETY.search(rank_candidates(list(candidates)).rationale)
    assert match is not None, "the rationale carried no safety-basis clause"
    return match.group(0)


def _with_ancestry() -> DesignCandidate:
    return _cand(Chemistry.PRIME, eff=0.8, p_intended=0.8, offscore=0.3, ancestry="afr")


def _without_ancestry() -> DesignCandidate:
    return _cand(Chemistry.CAS9_NUCLEASE, eff=0.7, p_intended=0.7, offscore=0.3)


def _unsearched() -> DesignCandidate:
    return _cand(Chemistry.BASE_ABE, eff=0.6, p_intended=0.6).model_copy(update={"offtarget": None})


# -- which quantity the safety term took --------------------------------------


def test_a_mixed_ancestry_basis_says_it_is_mixed() -> None:
    """The middle case: some candidates ancestry-annotated, some not.

    This is what `any(...)` got wrong — it claimed the population-aware basis for the
    whole menu on the strength of one candidate.
    """
    sentence = _safety_sentence([_with_ancestry(), _without_ancestry()])
    assert "1 of 2 searched candidate(s)" in sentence
    assert "not all on the same basis" in sentence


def test_a_uniform_ancestry_basis_is_stated_without_qualification() -> None:
    """The positive extreme keeps the plain sentence — no count, no caveat."""
    sentence = _safety_sentence([_with_ancestry()])
    assert sentence == "the safety term uses the worst-affected ancestry"


def test_no_ancestry_annotation_anywhere_says_so() -> None:
    """The negative extreme, which a previous round wrote and which must survive."""
    sentence = _safety_sentence([_without_ancestry()])
    assert "the worst nominated site" in sentence
    assert "no candidate here carries ancestry annotation" in sentence


def test_the_mixed_basis_counts_only_the_searched_candidates() -> None:
    """An unsearched candidate is on neither side of the choice, so it is not a denominator.

    It took the maximum on safety and has neither an ancestry nor a worst site. Counting
    it would report "1 of 3" for a choice made between 2.
    """
    sentence = _safety_sentence([_with_ancestry(), _without_ancestry(), _unsearched()])
    assert "1 of 2 searched candidate(s)" in sentence, sentence
    assert "of 3 searched" not in sentence


def test_an_all_unsearched_menu_describes_no_basis_at_all() -> None:
    """The safety term was not computed, so neither basis applies."""
    rationale = rank_candidates([_unsearched()]).rationale
    assert "no off-target search was run" in rationale
    assert "worst-affected ancestry" not in rationale
    assert "worst nominated site" not in rationale


# -- the simplicity axis ------------------------------------------------------


def _pegrna(*, nicking: bool) -> PegRNA:
    return PegRNA(
        spacer=Spacer(sequence=DNASequence("A" * 20)),
        scaffold=DNASequence("GTTTAGAGCTAGAAATAGCAAG"),
        rtt=DNASequence("A" * 15),
        pbs=DNASequence("A" * 12),
        rtt_homology_3prime=6,
        nicking_guide=NickingGuide(
            spacer=Spacer(sequence=DNASequence("G" * 20)),
            placement=GenomicInterval(chrom="c", start=60, end=80, strand=Strand.MINUS),
            nick_offset=-50,
        )
        if nicking
        else None,
    )


def test_a_pe3_pegrna_is_less_simple_than_a_pe2_one() -> None:
    """The penalty must land on the reagent that needs a second guide cloned.

    `nicking_guide is not None` is the whole test, and inverting it penalised PE2 and
    spared PE3 — the simplicity axis then rewards the more complex reagent, which is
    R576's finding (a weight acting on the wrong axis) one module over.
    """
    pe2 = _cand(Chemistry.PRIME).model_copy(update={"pegrna": _pegrna(nicking=False)})
    pe3 = _cand(Chemistry.PRIME).model_copy(update={"pegrna": _pegrna(nicking=True)})
    assert score_candidate(pe3).simplicity < score_candidate(pe2).simplicity, (
        "a PE3 reagent is two guides to clone and must score lower on simplicity"
    )


# -- Pareto strictness --------------------------------------------------------


def test_domination_is_strict_so_a_tie_dominates_nothing() -> None:
    """`>` on at least one objective, not `>=`.

    Relaxed, two candidates with identical objective vectors each dominate the other and
    the front can drop both — and the front is what `--render-candidates 0` promises to
    draw in full.
    """
    a = _cand(Chemistry.PRIME, eff=0.6, p_intended=0.6, offscore=0.2)
    b = _cand(Chemistry.PRIME, eff=0.6, p_intended=0.6, offscore=0.2)
    scores = [score_candidate(a), score_candidate(b)]
    assert scores[0].as_vector() == scores[1].as_vector(), "the fixture must be a real tie"
    assert pareto_front(scores) == (0, 1), "neither member of a tie may be dominated"


def test_a_strictly_better_candidate_still_dominates() -> None:
    """The positive case, so the check above cannot pass by never dominating anything."""
    worse = score_candidate(_cand(Chemistry.PRIME, eff=0.2, p_intended=0.2, offscore=0.6))
    better = score_candidate(_cand(Chemistry.PRIME, eff=0.9, p_intended=0.9, offscore=0.0))
    assert pareto_front([worse, better]) == (1,), "only the strictly better one survives"


# -- the cross-chemistry note -------------------------------------------------


def test_the_cross_chemistry_note_is_absent_from_a_single_chemistry_menu() -> None:
    """ "A note that always appears is not a note" — the code's own comment is the spec."""
    one = rank_candidates([_cand(Chemistry.PRIME), _cand(Chemistry.PRIME, eff=0.4)])
    assert CROSS_CHEMISTRY_NOTE not in one.rationale

    two = rank_candidates([_cand(Chemistry.PRIME), _cand(Chemistry.CAS9_NUCLEASE)])
    assert CROSS_CHEMISTRY_NOTE in two.rationale


# -- how many leaders are indistinguishable -----------------------------------


def test_a_candidate_exactly_at_the_tolerance_is_distinguishable() -> None:
    """The count is of candidates *within* tolerance, so the boundary is excluded.

    `leader.composite - s.composite < tolerance` draws the line. Relaxed to `<=`, a
    candidate exactly one tolerance behind the leader is reported as a co-leader — the
    rule then claims *less* resolution than the evidence gives, which is the safe
    direction and therefore the one nobody checks.

    Every number here is an exact binary fraction, so the comparison really does land on
    the boundary rather than a float's width away from it: the tolerance is
    ``1.0 * (0.25 - 0.0)`` and the gap is ``1.0 - 0.75``.
    """
    at_boundary = [_score(1.0, (0.0, 0.25)), _score(0.75, None)]
    assert indistinguishable_leaders(at_boundary, weights=_ALL_EFFICIENCY) == 1, (
        "a candidate exactly one tolerance behind the leader is separable from it"
    )

    # And just inside it, which is what the rule exists to report.
    inside = [_score(1.0, (0.0, 0.25)), _score(0.8, None)]
    assert indistinguishable_leaders(inside, weights=_ALL_EFFICIENCY) == 2


def test_two_identical_candidates_are_indistinguishable_leaders() -> None:
    """The positive case for the same count."""
    a = score_candidate(_cand(Chemistry.PRIME, eff=0.7, p_intended=0.7, offscore=0.1))
    b = score_candidate(_cand(Chemistry.CAS9_NUCLEASE, eff=0.7, p_intended=0.7, offscore=0.1))
    assert indistinguishable_leaders([a, b], weights=DEFAULT_WEIGHTS.normalized()) == 2


@pytest.mark.parametrize("n", [0, 1])
def test_indistinguishable_leaders_handles_a_tiny_menu(n: int) -> None:
    """A menu too small to have a spread must not raise."""
    scores = [score_candidate(_cand(Chemistry.PRIME))] * n
    assert indistinguishable_leaders(scores, weights=DEFAULT_WEIGHTS.normalized()) >= 0
