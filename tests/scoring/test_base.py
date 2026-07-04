"""Tests for the Scorer protocol and the no-bare-float guard."""

from __future__ import annotations

import pytest

from alleleforge.model_zoo.registry import ModelCard
from alleleforge.scoring.base import BareFloatError, Scorer, ensure_prediction
from alleleforge.types.prediction import Prediction, UncertaintyMethod

_PRED: Prediction[float] = Prediction(
    value=0.7, interval=(0.6, 0.8), method=UncertaintyMethod.ENSEMBLE
)


def test_ensure_prediction_passes_prediction_through() -> None:
    assert ensure_prediction(_PRED) is _PRED


@pytest.mark.parametrize("bad", [0.5, 1, "0.5", None, [0.1, 0.2]])
def test_ensure_prediction_rejects_non_prediction(bad: object) -> None:
    with pytest.raises(BareFloatError, match="no bare floats"):
        ensure_prediction(bad, who="cas9_efficiency")


class _ToyScorer:
    name = "toy"

    def model_card(self) -> ModelCard:
        return ModelCard(
            name="toy",
            version="1",
            chemistry=None,
            training_data="none",
            intended_use="test",
            out_of_scope_use="anything real",
            license="MIT",
            citation="n/a",
            known_failure_modes=("documented test failure mode",),
        )

    def score(self, x: object) -> Prediction[float]:
        return _PRED


def test_toy_scorer_satisfies_protocol() -> None:
    scorer = _ToyScorer()
    assert isinstance(scorer, Scorer)
    result = ensure_prediction(scorer.score("ACGT"), who=scorer.name)
    assert result.method is UncertaintyMethod.ENSEMBLE
    assert scorer.model_card().license == "MIT"
