"""The ``Scorer`` protocol and the no-bare-float guard.

Every efficiency / outcome predictor in AlleleForge is a :class:`Scorer`: it
returns a calibrated :class:`~alleleforge.types.prediction.Prediction`, never a
bare float, and exposes the :class:`~alleleforge.model_zoo.registry.ModelCard`
that documents what it is and how it may be used.

:func:`ensure_prediction` is the runtime half of the uncertainty contract — a
guard the orchestration layer wraps scorer output in, so a scorer that forgets
the contract fails loudly at the seam instead of silently leaking a point
estimate downstream.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from alleleforge.model_zoo.registry import ModelCard
from alleleforge.types.prediction import Prediction


class BareFloatError(TypeError):
    """Raised when a scorer returns a bare number instead of a ``Prediction``."""


def ensure_prediction(result: object, *, who: str = "scorer") -> Prediction[Any]:
    """Return ``result`` if it is a :class:`Prediction`, else raise.

    Args:
        result: The value a scorer returned.
        who: A label for the scorer, used in the error message.

    Returns:
        The validated :class:`Prediction`.

    Raises:
        BareFloatError: If ``result`` is not a :class:`Prediction` (a bare float,
            int, or anything else).
    """
    if isinstance(result, Prediction):
        return result
    raise BareFloatError(
        f"{who} returned {type(result).__name__}, not a Prediction; every scorer must "
        "carry calibrated uncertainty (no bare floats)"
    )


@runtime_checkable
class Scorer(Protocol):
    """A predictor that returns a calibrated ``Prediction`` and exposes its card."""

    name: str

    def model_card(self) -> ModelCard:
        """Return the model card documenting this scorer."""
        ...

    def score(self, x: Any) -> Prediction[float]:
        """Return a calibrated prediction for input ``x``."""
        ...
