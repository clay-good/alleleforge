"""Scoring foundations (Phase 6): backbone embeddings, uncertainty, Scorer.

The reusable ML substrate every chemistry-specific predictor (Phases 7-9) builds
on: a swappable sequence-embedding backbone, calibrated-uncertainty machinery
(ensembles, evidential heads, quantiles, isotonic calibration, OOD detection),
and the :class:`Scorer` protocol with its no-bare-float guard. The whole substrate
runs in CI on a weight-free stub embedder; real backbones are gated behind the
``real_weights`` marker.
"""

from __future__ import annotations

from alleleforge.scoring.backbone import (
    CachedEmbedder,
    CaduceusEmbedder,
    Embedding,
    Evo2Embedder,
    NucleotideTransformerEmbedder,
    SequenceEmbedder,
    StubEmbedder,
    sequence_hash,
)
from alleleforge.scoring.base import BareFloatError, Scorer, ensure_prediction
from alleleforge.scoring.uncertainty import (
    DEFAULT_ENSEMBLE_SIZE,
    DEFAULT_INTERVAL_LEVEL,
    DeepEnsemble,
    EnsembleResult,
    EvidentialParams,
    IsotonicCalibrator,
    OODDetector,
    ensemble_prediction,
    evidential_prediction,
    expected_calibration_error,
    quantile_prediction,
    to_prediction,
)

__all__ = [
    "DEFAULT_ENSEMBLE_SIZE",
    "DEFAULT_INTERVAL_LEVEL",
    "BareFloatError",
    "CachedEmbedder",
    "CaduceusEmbedder",
    "DeepEnsemble",
    "Embedding",
    "EnsembleResult",
    "EvidentialParams",
    "Evo2Embedder",
    "IsotonicCalibrator",
    "NucleotideTransformerEmbedder",
    "OODDetector",
    "Scorer",
    "SequenceEmbedder",
    "StubEmbedder",
    "ensemble_prediction",
    "ensure_prediction",
    "evidential_prediction",
    "expected_calibration_error",
    "quantile_prediction",
    "sequence_hash",
    "to_prediction",
]
