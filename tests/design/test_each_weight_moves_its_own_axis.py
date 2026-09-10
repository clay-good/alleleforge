"""A ranking weight must act on the axis it is named after.

`score_candidate` writes the composite out longhand::

    w["efficiency"] * eff + w["cleanliness"] * clean
    + w["safety"] * safe + w["simplicity"] * simple

Four names on the left, four values on the right, paired by hand. Exchanging two of them
is a one-character edit and there was nothing to catch it: swapping `cleanliness` and
`safety` leaves the whole suite green (4,224 passed). The reason is worth writing down —
`DEFAULT_WEIGHTS` gives cleanliness and safety **0.30 each**, so under the defaults the
swap is arithmetically invisible, and the one test that varies weights
(`test_weights_are_sensitive_in_the_expected_direction`) leaves the other two axes at
their defaults and holds cleanliness constant across its two candidates.

`safety` is `1 - worst-case off-target score`. A user who ranks a menu with
`--weights 0.2,0.1,0.6,0.1` because off-target risk is what they care about would, under
that swap, be ranking on outcome purity instead — a plausible menu, in a plausible order,
answering a different question, with the requested weights faithfully echoed back in the
run's provenance.

Two guards, both derived from `OBJECTIVES` so a fifth axis is covered the day it lands:
the composite *is* the dot product of the reported axes with their weights, and weighting
one axis alone ranks on that axis.
"""

from __future__ import annotations

import itertools

import pytest

from alleleforge.design.ranking import (
    DEFAULT_WEIGHTS,
    OBJECTIVES,
    RankingWeights,
    rank_candidates,
    score_candidate,
)
from alleleforge.types.candidate import DesignCandidate
from alleleforge.types.edit import AlleleOutcome, Chemistry, EditOutcome
from alleleforge.types.offtarget import OffTargetReport, OffTargetSite, ScoreMethod
from alleleforge.types.prediction import Prediction, UncertaintyMethod
from alleleforge.types.sequence import GenomicInterval, Strand


def _candidate(
    *,
    chemistry: Chemistry = Chemistry.CAS9_NUCLEASE,
    eff: float = 0.5,
    p_intended: float = 0.5,
    offscore: float = 0.0,
) -> DesignCandidate:
    sites = (
        ()
        if offscore == 0.0
        else (
            OffTargetSite(
                locus=GenomicInterval(chrom="chr9", start=10, end=30, strand=Strand.PLUS),
                mismatches=2,
                score=offscore,
                score_method=ScoreMethod.CFD,
            ),
        )
    )
    return DesignCandidate(
        chemistry=chemistry,
        efficiency=Prediction[float](
            value=eff,
            interval=(max(0.0, eff - 0.1), min(1.0, eff + 0.1)),
            method=UncertaintyMethod.HEURISTIC,
        ),
        outcome=EditOutcome(
            alleles=(
                AlleleOutcome(allele="EDIT", probability=p_intended, is_intended=True),
                AlleleOutcome(allele="WT", probability=1.0 - p_intended),
            )
        ),
        offtarget=OffTargetReport(spacer="A" * 20, pam="NGG", sites=sites),
        rationale="seed",
    )


#: One pair per axis: identical candidates but for the axis named, the second better on
#: it. `simplicity` is not a number a candidate carries — it is derived from how many
#: parts the reagent has — so its pair is the chemistry that has fewest against one that
#: has more, with every other input held equal.
_PAIRS = {
    "efficiency": (_candidate(eff=0.2), _candidate(eff=0.9)),
    "cleanliness": (_candidate(p_intended=0.2), _candidate(p_intended=0.9)),
    "safety": (_candidate(offscore=0.8), _candidate(offscore=0.0)),
    "simplicity": (
        _candidate(chemistry=Chemistry.PRIME),
        _candidate(chemistry=Chemistry.CAS9_NUCLEASE),
    ),
}


def test_there_is_a_pair_for_every_axis() -> None:
    """A missing pair would silently drop an axis out of the sweep below."""
    assert set(_PAIRS) == set(OBJECTIVES), sorted(set(OBJECTIVES) ^ set(_PAIRS))


@pytest.mark.parametrize("axis", OBJECTIVES)
def test_the_pair_for_an_axis_differs_on_that_axis_alone(axis: str) -> None:
    """Otherwise "the better one won" could be about some other axis entirely."""
    worse, better = (score_candidate(c) for c in _PAIRS[axis])
    moved = [name for name in OBJECTIVES if getattr(worse, name) != getattr(better, name)]
    assert moved == [axis], f"{axis}'s pair also moves {sorted(set(moved) - {axis})}"
    assert getattr(better, axis) > getattr(worse, axis)


def _only(axis: str) -> RankingWeights:
    """All the weight on one axis. Zero elsewhere is legal; all-zero is not."""
    return RankingWeights(**{name: (1.0 if name == axis else 0.0) for name in OBJECTIVES})


@pytest.mark.parametrize("axis", OBJECTIVES)
def test_weighting_one_axis_ranks_on_that_axis(axis: str) -> None:
    """The directional half: the weight named `axis` must move `axis`."""
    worse, better = _PAIRS[axis]
    ranked = rank_candidates([worse, better], weights=_only(axis))
    top = score_candidate(ranked.candidates[0], weights=_only(axis))
    assert getattr(top, axis) == getattr(score_candidate(better), axis)


@pytest.mark.parametrize(("axis", "other"), [p for p in itertools.permutations(OBJECTIVES, 2)])
def test_a_weight_does_not_move_a_different_axis(axis: str, other: str) -> None:
    """The half that catches an exchange: `other`'s pair must not respond to `axis`.

    Weighting `safety` alone over a pair that differs only in cleanliness leaves the two
    composites equal. Under a swapped pairing one of them wins, which is the whole defect
    this file exists for, stated without reference to which pair was exchanged.
    """
    worse, better = _PAIRS[other]
    weights = _only(axis)
    assert score_candidate(worse, weights=weights).composite == pytest.approx(
        score_candidate(better, weights=weights).composite
    )


_WEIGHT_VECTORS = [
    DEFAULT_WEIGHTS,
    RankingWeights(efficiency=0.2, cleanliness=0.1, safety=0.6, simplicity=0.1),
    RankingWeights(efficiency=0.1, cleanliness=0.6, safety=0.2, simplicity=0.1),
    RankingWeights(efficiency=0.7, cleanliness=0.1, safety=0.1, simplicity=0.1),
    RankingWeights(efficiency=3.0, cleanliness=2.0, safety=1.0, simplicity=4.0),  # unnormalized
]


@pytest.mark.parametrize("weights", _WEIGHT_VECTORS, ids=lambda w: str(w.normalized()))
@pytest.mark.parametrize("axis", OBJECTIVES)
def test_the_composite_is_the_axes_dotted_with_their_own_weights(
    axis: str, weights: RankingWeights
) -> None:
    """The total form: whatever the candidate, the sum pairs each name with itself.

    Asserted against the *reported* per-axis values, which is what a reader of the menu
    sees — so this fails for a mispaired weight and also for a composite computed from
    some quantity the score does not disclose.
    """
    for candidate in _PAIRS[axis]:
        score = score_candidate(candidate, weights=weights)
        normalized = weights.normalized()
        expected = sum(normalized[name] * getattr(score, name) for name in OBJECTIVES)
        assert score.composite == pytest.approx(expected)


def test_the_defaults_are_why_a_swap_was_invisible() -> None:
    """Recorded, because it is the reason the guard above has to exist.

    Two axes at the same default weight make an exchange of the two a no-op under the
    defaults, so every test that does not set weights is blind to it by construction.
    """
    equal = [
        pair
        for pair in itertools.combinations(OBJECTIVES, 2)
        if getattr(DEFAULT_WEIGHTS, pair[0]) == getattr(DEFAULT_WEIGHTS, pair[1])
    ]
    assert equal, (
        "no two default weights are equal any more — the sweep above is still the "
        "right check, but this note about why it was needed is stale"
    )
