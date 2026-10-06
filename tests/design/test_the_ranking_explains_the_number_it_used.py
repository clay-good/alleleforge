"""The ranking's explanations, counts, and defaults, pinned where a sweep found them loose.

A constant-and-operator mutation sweep of `design/ranking.py` left 21 of 135 alive. Six
are equivalent (`zip(strict=...)` over index-aligned vectors, a default for a chemistry
every enum member overrides, a zero floor the simplicity score never reaches). Six are
the per-chemistry simplicity heuristics, which no spec fixes: a 10% shift that keeps
their order is a tuning choice, not a defect, so only their documented properties are
pinned (inside [0, 1], fewer parts score higher).

The rest put a wrong statement in the rationale a user reads beside the rank:

* an in-distribution candidate described as "OOD, ranked on lower bound";
* the OOD sentence quoting the upper bound as the lower;
* the out-of-distribution count doubled;
* two tied leaders left without the note that their order is not resolved;
* an unscored candidate, an OOD floor, and a missing outcome scoring above zero.
"""

from __future__ import annotations

import dataclasses

import pytest

from alleleforge.design.ranking import (
    DEFAULT_WEIGHTS,
    rank_candidates,
    score_candidate,
)
from alleleforge.types.candidate import DesignCandidate
from alleleforge.types.edit import Chemistry
from alleleforge.types.prediction import Prediction, UncertaintyMethod
from tests.design.test_ranking import _cand, _report


def test_an_in_distribution_score_is_not_explained_as_ood() -> None:
    text = score_candidate(_cand(Chemistry.CAS9_NUCLEASE, eff=0.7)).explain()
    assert "OOD" not in text


def test_the_ood_explanation_quotes_the_lower_bound() -> None:
    # eff 0.7 OOD -> interval (0.6, 0.8); the sentence must name 0.60, not 0.80.
    text = score_candidate(_cand(Chemistry.PRIME, eff=0.7, in_distribution=False)).explain()
    assert "ranked on lower bound 0.60" in text


def test_the_rationale_counts_each_ood_candidate_once() -> None:
    outcome = rank_candidates(
        [
            _cand(Chemistry.CAS9_NUCLEASE, eff=0.8, in_distribution=False),
            _cand(Chemistry.CAS9_NUCLEASE, eff=0.5),
        ]
    )
    assert " 1 out-of-distribution candidate(s)" in outcome.rationale


def test_two_tied_leaders_are_called_unresolved() -> None:
    tied = [_cand(Chemistry.CAS9_NUCLEASE, eff=0.5), _cand(Chemistry.CAS9_NUCLEASE, eff=0.5)]
    assert "The top 2 candidates are within" in rank_candidates(tied).rationale


def test_an_unscored_candidate_contributes_nothing_and_is_not_called_ood() -> None:
    bare = DesignCandidate(chemistry=Chemistry.CAS9_NUCLEASE, offtarget=_report(0.0))
    score = score_candidate(bare)
    assert score.efficiency == 0.0 and score.cleanliness == 0.0
    assert score.efficiency_in_distribution is True
    # The rationale always explains the OOD rule; what must be absent is the count.
    assert "out-of-distribution candidate(s) were ranked" not in rank_candidates([bare]).rationale


def test_an_ood_lower_bound_of_zero_ranks_at_zero() -> None:
    zero_floor = Prediction[float](
        value=0.1, interval=(0.0, 0.3), method=UncertaintyMethod.HEURISTIC, in_distribution=False
    )
    candidate = _cand(Chemistry.PRIME).model_copy(update={"efficiency": zero_floor})
    assert score_candidate(candidate).efficiency == 0.0


@pytest.mark.parametrize("chemistry", list(Chemistry))
def test_simplicity_stays_inside_the_unit_interval(chemistry: Chemistry) -> None:
    assert 0.0 <= score_candidate(_cand(chemistry)).simplicity <= 1.0


def test_the_ranking_records_cannot_be_edited_after_the_fact() -> None:
    # DEFAULT_WEIGHTS is a module global every call shares; a score and an outcome are
    # what a report is built from. None of them may change underneath a reader.
    outcome = rank_candidates([_cand(Chemistry.CAS9_NUCLEASE)])
    for record, field in (
        (DEFAULT_WEIGHTS, "efficiency"),
        (outcome.scores[0], "efficiency"),
        (outcome, "rationale"),
    ):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(record, field, 0.0)
