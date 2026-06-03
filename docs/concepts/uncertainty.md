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
