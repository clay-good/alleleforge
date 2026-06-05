"""Base-editing window-outcome prediction.

The hard part of base editing is the *window outcome*: of the editable bases in
the activity window, which get edited, and what bystanders ride along. This
module predicts the distribution over window alleles and derives two calibrated
quantities the designer ranks on:

* ``p_intended_exact`` — the probability of the **exact** intended allele (the
  target base edited and **no** bystander edited).
* ``bystander_burden`` — the expected number of bystander edits.

The default is a transparent, deterministic baseline: each editable base in the
window is edited with a probability that peaks mid-window and is modulated by the
deaminase's motif preference (e.g. APOBEC1's TC motif); positions are treated as
independent, and the 2^k window alleles are enumerated. The trained BE-DICT
(default) and BE-Hive models load through the license-gated model zoo when
present; an ensemble mode reports their top-allele agreement.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass

from alleleforge.enumerate.base_editor import BaseEditor
from alleleforge.model_zoo.loader import WeightGate
from alleleforge.model_zoo.registry import ModelCard, ModelRegistry, default_registry
from alleleforge.types.edit import AlleleOutcome, EditOutcome
from alleleforge.types.guide import BaseEditWindow
from alleleforge.types.prediction import Prediction, UncertaintyMethod

#: Baseline peak per-base editing probability at the window center.
_PEAK_EDIT = 0.6

#: Heuristic interval half-width for the baseline's calibrated predictions.
_INTERVAL_HALF = 0.15


@dataclass(frozen=True)
class WindowOutcome:
    """A predicted base-edit window outcome with its derived quantities."""

    outcome: EditOutcome
    p_intended_exact: Prediction[float]
    bystander_burden: Prediction[float]


def _position_efficiency(position: int, window: tuple[int, int]) -> float:
    """Return a 0-1 position weight peaking at the window center."""
    lo, hi = window
    center = (lo + hi) / 2.0
    half = max(1.0, (hi - lo) / 2.0)
    return max(0.1, 1.0 - abs(position - center) / (half + 1.0))


def _edit_probability(
    position: int, spacer: str, editor: BaseEditor, window: tuple[int, int]
) -> float:
    """Return the probability the base at ``position`` is edited."""
    prob = _PEAK_EDIT * _position_efficiency(position, window)
    if editor.motif_preference is not None and position >= 2:
        neighbor = spacer[position - 2]  # the 5' neighbor of the editable base
        prob *= 1.3 if neighbor == editor.motif_preference else 0.5
    return min(0.99, max(0.0, prob))


def _allele(edited: frozenset[int], editor: BaseEditor) -> str:
    """Return an allele descriptor for an edited-position set."""
    if not edited:
        return "wildtype"
    return ";".join(f"{editor.target_base}{p}{editor.result_base}" for p in sorted(edited))


class BaseEditOutcomePredictor:
    """A transparent window-outcome baseline (the BE-DICT mechanism)."""

    name = "be-dict-baseline"

    def __init__(self, *, registry: ModelRegistry | None = None) -> None:
        """Configure the (optional) model-card registry."""
        self._registry = registry or default_registry()

    def model_card(self) -> ModelCard:
        """Return the BE-DICT model card (mechanism this baseline mirrors)."""
        return self._registry.get("be-dict")

    def predict(self, window: BaseEditWindow, editor: BaseEditor) -> WindowOutcome:
        """Predict the window-outcome distribution and derived quantities.

        Args:
            window: The placed base-edit window (target + bystander positions).
            editor: The base editor (provides the motif preference and bases).

        Returns:
            A :class:`WindowOutcome` with the allele distribution,
            ``p_intended_exact``, and ``bystander_burden``.
        """
        spacer = str(window.spacer.sequence)
        editable = sorted({*window.target_positions, *window.bystander_positions})
        probs = {p: _edit_probability(p, spacer, editor, window.window) for p in editable}

        alleles: list[AlleleOutcome] = []
        intended = frozenset(window.target_positions)
        for r in range(len(editable) + 1):
            for subset in itertools.combinations(editable, r):
                s = frozenset(subset)
                prob = 1.0
                for p in editable:
                    prob *= probs[p] if p in s else 1.0 - probs[p]
                alleles.append(
                    AlleleOutcome(
                        allele=_allele(s, editor), probability=prob, is_intended=s == intended
                    )
                )
        outcome = EditOutcome(alleles=tuple(alleles), partial=False)

        p_exact = next((a.probability for a in alleles if a.is_intended), 0.0)
        burden = sum(probs[p] for p in window.bystander_positions)
        return WindowOutcome(
            outcome=outcome,
            p_intended_exact=_prediction(p_exact),
            bystander_burden=_prediction(burden),
        )


def _prediction(value: float) -> Prediction[float]:
    """Wrap a baseline scalar in a calibrated 80% heuristic prediction."""
    return Prediction[float](
        value=value,
        interval=(max(0.0, value - _INTERVAL_HALF), value + _INTERVAL_HALF),
        interval_level=0.80,
        method=UncertaintyMethod.HEURISTIC,
        in_distribution=True,
        calibrated=False,
    )


def recommend_window(
    scored: Sequence[tuple[BaseEditWindow, WindowOutcome]],
) -> tuple[BaseEditWindow, WindowOutcome] | None:
    """Return the editor/guide maximizing clean-edit probability.

    The recommendation prefers the highest ``p_intended_exact`` and, on a tie,
    the lower ``bystander_burden`` — surfacing the cleanliness/bystander tradeoff.
    """
    if not scored:
        return None
    return max(
        scored,
        key=lambda sw: (sw[1].p_intended_exact.value, -sw[1].bystander_burden.value),
    )


class _ModelZooAdapter(WeightGate):
    """Shared base for the trained base-edit outcome adapters (lazy, gated).

    Trained weights resolve through the **consent-gated, checksum-verified** model
    zoo (:class:`~alleleforge.model_zoo.loader.WeightGate`); the forward pass over
    those weights lands with the real-weights integration. Use
    :class:`BaseEditOutcomePredictor` meanwhile.
    """

    name = ""

    def model_card(self) -> ModelCard:
        """Return the adapter's model card (raises if not registered)."""
        return self._registry.get(self.card_name)

    def predict(self, window: BaseEditWindow, editor: BaseEditor) -> WindowOutcome:
        """Resolve weights (consent-gated), then predict the window outcome.

        Raises:
            ConsentError / LicenseError / ChecksumError: From the weight gate.
            NotImplementedError: The trained forward pass is not yet wired.
        """
        self.resolve_weights()
        raise NotImplementedError(  # pragma: no cover - forward pass needs real weights
            f"{self.name} weights resolved and verified; the trained forward pass is "
            "wired alongside the real-weights integration. Use "
            "BaseEditOutcomePredictor meanwhile."
        )


class BeDictAdapter(_ModelZooAdapter):
    """Adapter to the trained BE-DICT model (default base-edit outcome)."""

    name = "BE-DICT"
    card_name = "be-dict"


class BeHiveAdapter(_ModelZooAdapter):
    """Adapter to the trained BE-Hive model (optional)."""

    name = "BE-Hive"
    card_name = "be-hive"
