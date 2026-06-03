# The uncertainty contract

A confident wrong answer is worse than a wide honest one. AlleleForge enforces this structurally:
**no scorer returns a bare float.** Every efficiency or outcome prediction is a
[`Prediction[T]`][alleleforge.types.prediction.Prediction] carrying:

- a point estimate (`value`);
- a calibrated predictive `interval` (default **80%**, the `interval_level`);
- the `method` that produced the interval (deep ensemble, evidential, quantile, conformal, …);
- an `in_distribution` flag — `False` when the input is unlike the model's training distribution;
- a `calibrated` flag recording whether the interval was post-hoc calibrated.

When the payload is numeric, the point estimate is required to lie inside the interval; structured
payloads (such as an outcome distribution) carry an interval over a derived scalar instead.

## Why 80%

An 80% predictive interval is wide enough to be honest about model error yet narrow enough to rank
candidates. It is the spec-mandated default and is overridable per call. The level is always stored
alongside the bounds so downstream consumers never assume a coverage that was not produced.

## Combining predictions

Independent predictions combine through [`Prediction.combine`][alleleforge.types.prediction.Prediction.combine],
which propagates the honesty flags conservatively: the combined result is `calibrated` only if every
input was, and `in_distribution` only if every input was.

## How the interval is produced (Phase 6)

The `alleleforge.scoring.uncertainty` module turns a model's raw output into a `Prediction`. It is
pure stdlib (no numpy/torch), so the whole substrate is exercised in CI on a weight-free stub
embedder.

| Method | When | How the interval is formed |
|---|---|---|
| **Deep ensemble** (default, N=5) | the production path | Gaussian band `mean ± z·σ` from member **disagreement** — it widens automatically on out-of-distribution inputs where members diverge |
| **Evidential** | single-model fallback | a Normal-Inverse-Gamma head splitting **aleatoric** (data) from **epistemic** (model) variance |
| **Quantile** | when the model emits quantiles | the interval is read straight off the `(1−level)/2` and `(1+level)/2` quantiles |

Post-hoc **isotonic calibration** (`IsotonicCalibrator`, a pool-adjacent-violators fit) maps raw
scores to calibrated ones; `expected_calibration_error` quantifies the improvement and is a
first-class metric on every CRISPR-Bench task (Phase 14).

## Out-of-distribution honesty

`in_distribution` is not guesswork. The `OODDetector` stores a training-set reference in
**embedding space** (from the swappable [`SequenceEmbedder`][alleleforge.scoring.backbone.SequenceEmbedder]
backbone — Nucleotide Transformer v2 by default) and flags an input whose nearest-reference distance
exceeds a threshold derived from the reference's own density. A prime-editing target outside PRIDICT's
HEK293T/K562 training context, for example, is flagged rather than silently scored — the honesty *is*
the product.
