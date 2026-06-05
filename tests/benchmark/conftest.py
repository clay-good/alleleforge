"""Shared stub scorers and a fixed timestamp for the Phase 14 benchmark tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from alleleforge.model_zoo.registry import ModelCard
from alleleforge.types.prediction import Prediction, UncertaintyMethod

#: A fixed timestamp so signed results are reproducible in tests.
FIXED_TS = datetime(2024, 5, 1, tzinfo=UTC)


def _card(name: str) -> ModelCard:
    """Return a minimal, valid model card for a stub scorer."""
    return ModelCard(
        name=name,
        version="0",
        chemistry=None,
        training_data="none (test stub)",
        intended_use="benchmark testing",
        out_of_scope_use="anything real",
        license="MIT",
        citation="AlleleForge test suite",
    )


class StubRegressionScorer:
    """A constant-prediction regression scorer (a marginal baseline stand-in)."""

    name = "stub-regression"

    def __init__(self, value: float = 0.5, *, in_distribution: bool = True) -> None:
        self._value = value
        self._in_dist = in_distribution

    def model_card(self) -> ModelCard:
        return _card(self.name)

    def score(self, x: Any) -> Prediction[Any]:
        return Prediction[float](
            value=self._value,
            interval=(max(0.0, self._value - 0.2), min(1.0, self._value + 0.2)),
            method=UncertaintyMethod.HEURISTIC,
            in_distribution=self._in_dist,
        )


class StubDistributionScorer:
    """A scorer returning a fixed outcome distribution."""

    name = "stub-distribution"

    def __init__(self, distribution: dict[str, float]) -> None:
        self._distribution = distribution

    def model_card(self) -> ModelCard:
        return _card(self.name)

    def score(self, x: Any) -> Prediction[Any]:
        return Prediction[dict[str, float]](
            value=dict(self._distribution),
            interval=(0.0, 1.0),
            method=UncertaintyMethod.HEURISTIC,
        )


class StubClassifierScorer:
    """A mismatch-driven classifier over off-target candidate pairs."""

    name = "stub-classifier"

    def model_card(self) -> ModelCard:
        return _card(self.name)

    def score(self, x: Any) -> Prediction[Any]:
        mm = float(x["mismatches"]) if isinstance(x, dict) else 0.0
        p = max(0.01, min(0.99, 1.0 - mm / 6.0))
        return Prediction[float](value=p, interval=(0.0, 1.0), method=UncertaintyMethod.HEURISTIC)


@pytest.fixture
def fixed_ts() -> datetime:
    """Return the fixed reproducible timestamp."""
    return FIXED_TS
