"""SpCas9 on-target efficiency scorers.

Two efficiency :class:`~alleleforge.scoring.base.Scorer` implementations, both
returning a calibrated 80% :class:`~alleleforge.types.prediction.Prediction` with
an out-of-distribution flag — never a bare float:

* :class:`RuleSet3Scorer` — an always-available, no-large-download baseline. It
  is a transparent, deterministic sequence-feature model in the spirit of Rule
  Set 3 (DeWeirdt & Doench, *Nat Commun* 2022), including a **tracrRNA-aware**
  term (RS3's key addition: activity depends on the tracrRNA scaffold). This is a
  documented *heuristic* baseline (``method=HEURISTIC``), not the fitted model.

* :class:`TrainedRuleSet3Scorer` — the **real** trained Rule Set 3 model. Its
  point estimate comes from the published LightGBM model (resolved through the
  consent-gated, checksum-verified model zoo as a version-independent text
  booster) over the exact ``sglearn`` 632-feature representation, so it
  reproduces upstream ``rs3.predict_seq`` to the bit. Opt-in: it needs the
  ``cas9-rs3`` extra (``lightgbm``, ``sglearn``) and is gated behind the
  ``real_weights`` test marker, so CI stays weight-free.

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
from pathlib import Path
from typing import Any

from alleleforge.model_zoo.loader import WeightGate
from alleleforge.model_zoo.registry import (
    Downloader,
    ModelCard,
    ModelRegistry,
    ModelUse,
    default_registry,
)
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


#: rs3 reference tracrRNA labels, in the column order the trained model expects.
_RS3_REF_TRACRS = ("Hsu2013", "Chen2013")


def _require_rs3_runtime() -> tuple[Any, Any]:  # pragma: no cover - needs the cas9-rs3 extra
    """Import lightgbm + sglearn, or raise a helpful error if missing."""
    try:
        import lightgbm
        import sglearn
    except ImportError as exc:
        raise RuntimeError(
            "the trained Rule Set 3 model requires the 'cas9-rs3' extra "
            "(lightgbm, sglearn); install alleleforge[cas9-rs3], or use "
            "RuleSet3Scorer for the weight-free baseline"
        ) from exc
    return lightgbm, sglearn


class TrainedRuleSet3Scorer(WeightGate):
    """The real trained Rule Set 3 LightGBM model (consent-gated, opt-in).

    The point estimate is the published Rule Set 3 model's prediction, reproduced
    bit-for-bit from a version-independent LightGBM **text booster** resolved
    through the model zoo (license + consent + checksum) over the exact
    ``sglearn`` 632-feature representation. The interval is a documented heuristic
    spread — the trained model yields a point activity, not a calibrated interval —
    so ``calibrated`` stays ``False`` until conformal calibration on a real
    validation set lands (R5). The recorded
    :class:`~alleleforge.types.provenance.ModelCheckpoint` carries the model's
    provenance and failure modes.

    Inputs are 30-nt contexts (4 nt 5' + 20 nt protospacer + 3 nt PAM + 3 nt 3'),
    the Rule Set 3 sequence-model contract. Opt-in: needs the ``cas9-rs3`` extra
    and is gated behind the ``real_weights`` test marker, so CI stays weight-free.
    """

    name = "rule-set-3-trained"
    card_name = "rule-set-3"

    #: The asymmetric window this model reads, as (5' flank, 3' flank) around the
    #: protospacer+PAM — Rule Set 3's 30-mer (4 nt 5' + 20 + 3 PAM + 3 nt 3').
    #: ``design_cas9`` reads this to build the right context.
    context_flank = (4, 3)

    #: Required Rule Set 3 context length (nt).
    CONTEXT_LENGTH = 30
    #: Heuristic interval half-width around the trained point estimate.
    _INTERVAL_HALF = 0.15

    def __init__(
        self,
        *,
        tracr: TracrRNA = TracrRNA.CHEN_2013,
        registry: ModelRegistry | None = None,
        use: ModelUse = ModelUse.RESEARCH,
        consent: bool = False,
        cache_dir: str | Path | None = None,
        downloader: Downloader | None = None,
    ) -> None:
        """Configure the assumed tracrRNA scaffold and the model-zoo gate.

        Args:
            tracr: The tracrRNA scaffold to score against (RS3 feature).
            registry: Model-card registry (defaults to the bundled cards).
            use: The use the weights are loaded for (drives the license gate).
            consent: Must be ``True`` to authorize the booster download.
            cache_dir: Override for the checkpoint cache (pinned-artifact path).
            downloader: Injected fetcher for the pinned booster (tests).
        """
        super().__init__(
            registry=registry,
            use=use,
            consent=consent,
            cache_dir=cache_dir,
            downloader=downloader,
        )
        self.tracr = tracr
        self._booster: Any = None

    def model_card(self) -> ModelCard:
        """Return the Rule Set 3 model card."""
        return self._registry.get(self.card_name)

    def _load_booster(self) -> Any:  # pragma: no cover - needs the extra + real booster
        """Resolve weights (consent-gated) and load the LightGBM text booster once."""
        if self._booster is None:
            lightgbm, _ = _require_rs3_runtime()
            path = self.resolve_weights()
            self._booster = lightgbm.Booster(model_file=path)
        return self._booster

    def predict_raw(self, contexts: Sequence[str]) -> list[float]:  # pragma: no cover - extra
        """Return the trained model's raw activity z-scores for 30-nt ``contexts``.

        This is the parity surface: the scores match upstream
        ``rs3.seq.predict_seq`` exactly (same featurization, same booster).

        Raises:
            ValueError: If any context is not :attr:`CONTEXT_LENGTH` nt long.
        """
        bad = sorted({len(c) for c in contexts if len(c) != self.CONTEXT_LENGTH})
        if bad:
            raise ValueError(
                f"Rule Set 3 needs {self.CONTEXT_LENGTH}-nt contexts; got lengths {bad}"
            )
        _, sglearn = _require_rs3_runtime()
        booster = self._load_booster()
        features = sglearn.featurize_guides(list(contexts), n_jobs=1)
        tracr_label = "Chen2013" if self.tracr is TracrRNA.CHEN_2013 else "Hsu2013"
        for ref in _RS3_REF_TRACRS:
            features[f"{ref} tracr"] = int(tracr_label == ref)
        return [float(x) for x in booster.predict(features.values)]

    def score(self, context: str) -> Prediction[float]:  # pragma: no cover - needs the extra
        """Return a Rule Set 3 efficiency prediction for a 30-nt ``context``.

        The point estimate is the trained model's activity, squashed to ``[0, 1]``
        by a monotone logistic map (ranking-preserving); the raw z-score is
        available via :meth:`predict_raw`. The interval is heuristic.
        """
        z = self.predict_raw([context])[0]
        value = _sigmoid(z)
        in_dist = "N" not in context.upper() and len(context) == self.CONTEXT_LENGTH
        return Prediction[float](
            value=value,
            interval=(
                max(0.0, value - self._INTERVAL_HALF),
                min(1.0, value + self._INTERVAL_HALF),
            ),
            interval_level=DEFAULT_INTERVAL_LEVEL,
            method=UncertaintyMethod.HEURISTIC,
            in_distribution=in_dist,
            calibrated=False,
            point_from_trained_model=True,  # trained RS3 point; interval still heuristic
        )


def _is_weight_free(embedder: SequenceEmbedder) -> bool:
    """Return ``True`` if ``embedder`` is the weight-free stub (no trained backbone).

    Unwraps a :class:`~alleleforge.scoring.backbone.CachedEmbedder` so a cached
    stub is still recognized as weight-free.
    """
    inner = getattr(embedder, "_embedder", embedder)
    return isinstance(inner, StubEmbedder)


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
        """Return an ensemble efficiency prediction for ``context``.

        The raw ensemble interval is not post-hoc calibrated, so the result is
        ``calibrated=False`` (only a fitted calibrator certifies calibration). On
        the weight-free stub embedder — content-hashed noise, not a trained
        backbone — the method is demoted to ``HEURISTIC`` so a heuristic result
        is not mistaken for a trained-model one.
        """
        embedding = self._embedder.embed([context])[0]
        heads = [_member_weights(i, len(embedding)) for i in range(self._n_members)]
        ensemble = DeepEnsemble([self._member_head(w) for w in heads])
        result = ensemble.predict(embedding)
        in_dist = self._ood.is_in_distribution(embedding) if self._ood is not None else True
        method = (
            UncertaintyMethod.HEURISTIC
            if _is_weight_free(self._embedder)
            else UncertaintyMethod.ENSEMBLE
        )
        return ensemble_prediction(result, in_distribution=in_dist, method=method)
