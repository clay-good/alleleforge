# Scoring foundations reference

The `alleleforge.model_zoo` and `alleleforge.scoring` packages (Phase 6) are the
reusable ML substrate every chemistry-specific predictor (Phases 7–9) builds on:
a license-gated model zoo, a swappable sequence-embedding backbone, the
calibrated-uncertainty machinery, and the `Scorer` protocol. See
[The uncertainty contract](../concepts/uncertainty.md) for the design rationale.

The whole substrate runs in CI on a weight-free stub embedder; real backbones are
gated behind the `real_weights` test marker and require the `ml` extra.

## Model zoo registry

::: alleleforge.model_zoo.registry

## The Scorer protocol

::: alleleforge.scoring.base

## Backbone embeddings

::: alleleforge.scoring.backbone

## Calibrated uncertainty

::: alleleforge.scoring.uncertainty
