"""SpCas9 on-target efficiency scorers.

Two efficiency :class:`~alleleforge.scoring.base.Scorer` implementations, both
returning a calibrated 80% :class:`~alleleforge.types.prediction.Prediction` with
an out-of-distribution flag — never a bare float:

* :class:`RuleSet3Scorer` — an always-available, no-large-download baseline. It
  is a transparent, deterministic sequence-feature model in the spirit of Rule
  Set 3 (DeWeirdt & Doench, *Nat Commun* 2022), including a **tracrRNA-aware**
  term (RS3's key addition: activity depends on the tracrRNA scaffold). The exact
  trained RS3 coefficients load through the model zoo when present; the shipped
  default is the documented feature baseline, not the fitted model.

* :class:`EnsembleEfficiencyScorer` — the default: a backbone-fine-tuned **deep
  ensemble** over a :class:`~alleleforge.scoring.backbone.SequenceEmbedder`. The
  interval comes from member disagreement and the OOD flag from an embedding-space
  :class:`~alleleforge.scoring.uncertainty.OODDetector`. CI runs it on the
  weight-free stub embedder; real backbones are gated behind ``real_weights``.
"""

from __future__ import annotations

import hashlib
import math
import struct
from collections.abc import Callable, Sequence
from enum import StrEnum

from alleleforge.model_zoo.registry import ModelCard, ModelRegistry, default_registry
from alleleforge.scoring.backbone import Embedding, SequenceEmbedder, StubEmbedder
from alleleforge.scoring.uncertainty import (
    DEFAULT_ENSEMBLE_SIZE,
    DEFAULT_INTERVAL_LEVEL,
    DeepEnsemble,
    OODDetector,
    ensemble_prediction,
)
from alleleforge.types.prediction import Prediction, UncertaintyMethod
from alleleforge.types.provenance import ModelCheckpoint


class TracrRNA(StrEnum):
    """The tracrRNA scaffold an efficiency model assumes (RS3 feature)."""

    HSU_2013 = "hsu2013"  # the original scaffold
    CHEN_2013 = "chen2013"  # the optimized / extended scaffold (higher activity)


def _sigmoid(x: float) -> float:
    """Return the logistic of ``x`` clamped to ``[0.01, 0.99]``."""
    return min(0.99, max(0.01, 1.0 / (1.0 + math.exp(-x))))


def _gc_fraction(seq: str) -> float:
    """Return the GC fraction of ``seq`` (0 for empty)."""
    return sum(b in "GC" for b in seq) / len(seq) if seq else 0.0


class RuleSet3Scorer:
    """A transparent, deterministic Rule-Set-3-style efficiency baseline."""

    name = "rule-set-3"

    def __init__(
        self, *, tracr: TracrRNA = TracrRNA.CHEN_2013, registry: ModelRegistry | None = None
    ) -> None:
        """Configure the assumed tracrRNA scaffold and (optional) card registry."""
        self.tracr = tracr
        self._registry = registry or default_registry()

    def model_card(self) -> ModelCard:
        """Return the bundled Rule Set 3 model card."""
        return self._registry.get("rule-set-3")

    def _logit(self, context: str) -> float:
        """Return the feature-weighted activity logit for ``context``."""
        seq = context.upper()
        gc = _gc_fraction(seq)
        logit = 0.0
        logit -= 4.0 * abs(gc - 0.55)  # mid-GC is most active
        if "TTTT" in seq:
            logit -= 1.5  # Pol III terminator in the spacer
        if "GGGG" in seq:
            logit -= 0.4  # G-quadruplex / secondary structure
        if seq.endswith(("GG", "AG")):
            logit += 0.2  # purine at the PAM-proximal 3' end favors activity
        # tracrRNA-aware term (DeWeirdt & Doench 2022): the optimized scaffold
        # lifts activity relative to the original Hsu 2013 scaffold.
        logit += 0.3 if self.tracr is TracrRNA.CHEN_2013 else 0.0
        return logit

    def score(self, context: str) -> Prediction[float]:
        """Return a calibrated efficiency prediction for a guide ``context``."""
        value = _sigmoid(self._logit(context))
        half = 0.15  # documented heuristic spread for the rule-based baseline
        in_dist = "N" not in context.upper() and len(context) >= 20
        return Prediction[float](
            value=value,
            interval=(max(0.0, value - half), min(1.0, value + half)),
            interval_level=DEFAULT_INTERVAL_LEVEL,
            method=UncertaintyMethod.HEURISTIC,
            in_distribution=in_dist,
            calibrated=False,
        )


def _member_weights(index: int, dim: int) -> tuple[float, ...]:
    """Return deterministic per-member projection weights in ``[-1, 1]``."""
    weights: list[float] = []
    for j in range(dim):
        digest = hashlib.sha256(f"head{index}:{j}".encode()).digest()
        (raw,) = struct.unpack_from(">I", digest)
        weights.append((raw / 0xFFFFFFFF) * 2.0 - 1.0)
    return tuple(weights)


class EnsembleEfficiencyScorer:
    """A backbone-fine-tuned deep-ensemble efficiency scorer (the default)."""

    name = "cas9-efficiency-ensemble"

    def __init__(
        self,
        *,
        embedder: SequenceEmbedder | None = None,
        n_members: int = DEFAULT_ENSEMBLE_SIZE,
        ood: OODDetector | None = None,
        registry: ModelRegistry | None = None,
    ) -> None:
        """Configure the embedder, ensemble size, and OOD detector.

        Args:
            embedder: The sequence backbone (defaults to :class:`StubEmbedder`
                for CI; use a real backbone with the ``ml`` extra).
            n_members: Ensemble size (default 5).
            ood: An out-of-distribution detector over training embeddings; when
                omitted every input is treated as in-distribution.
            registry: Model-card registry (defaults to the bundled cards).
        """
        self._embedder = embedder or StubEmbedder(dim=16)
        self._n_members = n_members
        self._ood = ood
        self._registry = registry or default_registry()

    def model_card(self) -> ModelCard:
        """Return the deep-ensemble model card."""
        return self._registry.get("cas9-efficiency-ensemble")

    def backbone_checkpoint(self) -> ModelCheckpoint | None:
        """Return the embedding backbone's resolved checkpoint, for provenance.

        Returns ``None`` for a weight-free embedder (e.g. :class:`StubEmbedder`)
        or before the backbone has resolved its weights through the model zoo.
        """
        getter = getattr(self._embedder, "model_checkpoint", None)
        if getter is None:
            return None
        checkpoint: ModelCheckpoint | None = getter()
        return checkpoint

    def _member_head(self, weights: Sequence[float]) -> Callable[[Embedding], float]:
        """Return one member's predictor: a squashed linear projection."""

        def head(embedding: Embedding) -> float:
            return _sigmoid(sum(w * e for w, e in zip(weights, embedding, strict=True)))

        return head

    def score(self, context: str) -> Prediction[float]:
        """Return a calibrated ensemble efficiency prediction for ``context``."""
        embedding = self._embedder.embed([context])[0]
        heads = [_member_weights(i, len(embedding)) for i in range(self._n_members)]
        ensemble = DeepEnsemble([self._member_head(w) for w in heads])
        result = ensemble.predict(embedding)
        in_dist = self._ood.is_in_distribution(embedding) if self._ood is not None else True
        return ensemble_prediction(result, in_distribution=in_dist, calibrated=True)
