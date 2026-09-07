"""An objective weighted zero was disclosed as one decimal in a parenthetical.

    Ranked by a weighted sum of four higher-is-better objectives
    (efficiency 1.00, cleanliness 0.00, safety 0.00, simplicity 0.00);
    the safety term uses the worst-affected ancestry and …

`--weights 1,0,0,0` is a legitimate request, and the resulting menu may put the least
specific guide first. The report reads exactly like any other one: same layout, same
sentence, and it goes on to explain how the safety term works — a term that contributed
nothing to the order it is describing.

This project already refuses that shape elsewhere. `offtarget-not-searched` exists because
a safety axis nobody measured must not be typeset like one that was; the same holds for an
axis measured and then multiplied by zero, and for the same reason: the artifact is
forwarded to someone who did not choose the weights.

The note names the Pareto front as the part that still answers the question, which is
true by construction — `pareto_front` dominates on the raw objective vector and never sees
the weights.
"""

from __future__ import annotations

import pytest

from alleleforge.design.ranking import OBJECTIVES, RankingWeights, rank_candidates
from alleleforge.types.candidate import DesignCandidate


def _outcome(weights: RankingWeights, candidates: list[DesignCandidate]) -> object:
    return rank_candidates(candidates, weights=weights)


@pytest.fixture
def candidates(make_reference: object) -> list[DesignCandidate]:
    """A prime menu's candidates, ordered by whatever weights each test passes."""
    from alleleforge.design.designer import design
    from alleleforge.types.edit import EditIntent

    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[58:61] = list("CCA")
    reference = make_reference({"chr2": "".join(seq)})  # type: ignore[operator]
    menu = design(
        "chr2:71:A>C",
        reference=reference,
        intent=EditIntent.INSTALL,
        run_offtarget=False,
        max_candidates_per_chemistry=5,
    )
    assert len(menu.candidates) > 1, "need a menu to order"
    return list(menu.candidates)


def test_the_default_weights_say_nothing(candidates: list[DesignCandidate]) -> None:
    """A note that always fires is not a note."""
    outcome = _outcome(RankingWeights(), candidates)
    assert all(v > 0 for v in outcome.weights.values())
    assert "weighted zero" not in outcome.rationale


@pytest.mark.parametrize(
    "weights, named",
    [
        ((1.0, 0.0, 0.0, 0.0), "Cleanliness, safety and simplicity are weighted zero"),
        ((1.0, 1.0, 0.0, 0.0), "Safety and simplicity are weighted zero"),
        ((1.0, 1.0, 1.0, 0.0), "Simplicity is weighted zero"),
    ],
    ids=["three", "two", "one"],
)
def test_a_zeroed_objective_is_named(
    candidates: list[DesignCandidate], weights: tuple[float, ...], named: str
) -> None:
    outcome = _outcome(RankingWeights(**dict(zip(OBJECTIVES, weights, strict=True))), candidates)
    assert named in outcome.rationale, outcome.rationale


def test_the_note_says_the_ordering_does_not_reflect_it(
    candidates: list[DesignCandidate],
) -> None:
    outcome = _outcome(
        RankingWeights(efficiency=1.0, cleanliness=0.0, safety=0.0, simplicity=0.0), candidates
    )
    assert "does not reflect them at all" in outcome.rationale


def test_the_front_really_is_unaffected_by_the_weights(
    candidates: list[DesignCandidate],
) -> None:
    """The note's second half is a claim about the code; this is the code.

    If the front ever starts depending on the weights, the sentence pointing a reader at
    it as the unweighted view becomes false, and this fails rather than the prose rotting.
    """
    default = _outcome(RankingWeights(), candidates)
    skewed = _outcome(
        RankingWeights(efficiency=1.0, cleanliness=0.0, safety=0.0, simplicity=0.0),
        candidates,
    )

    def front_vectors(outcome: object) -> set[tuple[float, ...]]:
        # By objective vector, not by index or object identity: the two rankings order
        # the same candidates differently, and `rank_candidates` returns copies, so
        # both of those would compare the wrong things and fail for the wrong reason.
        return {outcome.scores[i].as_vector() for i in outcome.pareto_front}

    default_front, skewed_front = front_vectors(default), front_vectors(skewed)
    assert default_front, "an empty front would satisfy this trivially"
    assert default_front == skewed_front, (default_front, skewed_front)
