## MODIFIED Requirements

### Requirement: Out-of-distribution predictions widen, never narrow

When a prediction is flagged `in_distribution = False`, its interval SHALL be at least as
wide as the in-distribution interval it would otherwise have produced (widened, or its
`method` demoted), and SHALL additionally satisfy an **additive minimum half-width floor**
so it is strictly wider than any in-distribution interval the same head could emit — a
multiplicative widen alone is insufficient because it cannot rescue a zero- or near-zero
half-width. An out-of-distribution input can never present a narrow, confident interval
even when model members happen to agree exactly.

#### Scenario: Agreeing members on an OOD input
- **WHEN** ensemble members agree closely but the input is out of distribution
- **THEN** the returned interval is widened rather than narrow, and `calibrated = False`

#### Scenario: Perfectly agreeing members on an OOD input
- **WHEN** ensemble members return identical values (zero dispersion) on an
  out-of-distribution input
- **THEN** the returned interval still has non-zero width (the additive floor applies),
  never a zero-width confident interval

## ADDED Requirements

### Requirement: Scorers compute in_distribution and fail honest

Every scorer that emits a `Prediction` SHALL derive `in_distribution` from an explicit
distribution check appropriate to its inputs. A scorer with no distribution check wired
SHALL default `in_distribution = False` (fail-honest); it SHALL NOT hardcode
`in_distribution = True`. The default ensemble efficiency, prime, and base-editor scorers
SHALL ship a training reference or documented context check so OOD is actually computed in
the default design path, and a trained adapter (e.g. PRIDICT2) SHALL be no less OOD-honest
than the heuristic baseline it replaces.

#### Scenario: Detector-less scorer
- **WHEN** a scorer emits a prediction with no distribution check available
- **THEN** the prediction reports `in_distribution = False`, not `True`

#### Scenario: Default design path computes OOD
- **WHEN** the default design pipeline scores a target outside the model's training regime
- **THEN** the returned prediction reports `in_distribution = False`

#### Scenario: Trained path is not less honest than its baseline
- **WHEN** a trained efficiency adapter and its heuristic baseline both score a target
  outside the supported cell contexts
- **THEN** the trained adapter also flags the prediction out-of-distribution

### Requirement: Trained predictions are distinguishable from heuristics by their flags

The honesty surface SHALL let a consumer tell a trained point estimate (with a
not-yet-calibrated interval) from a fully heuristic prediction **without reading
provenance** — via a distinct `method` value or a boolean such as
`point_from_trained_model`. A trained model SHALL NOT present honesty flags byte-identical
to a pure heuristic baseline.

#### Scenario: Trained versus heuristic
- **WHEN** a trained scorer (e.g. Rule Set 3, PRIDICT2, BE-DICT, Lindel) and a heuristic
  baseline each emit a prediction
- **THEN** the two are distinguishable by the honesty surface alone, without inspecting the
  `ModelCheckpoint` or provenance

### Requirement: An unmeasured heuristic band is not asserted as measured coverage

A `calibrated = False` heuristic prediction SHALL NOT assert a specific numeric
`interval_level` it has not measured. Its fixed spread SHALL be represented as
nominal/unmeasured — carrying a note or an `interval_level` sentinel that marks the width
as a placeholder rather than measured coverage — so a fabricated coverage number cannot
masquerade as a measured one. A count-valued quantity SHALL NOT claim a probability-style
coverage band.

#### Scenario: Fixed heuristic band
- **WHEN** a heuristic scorer wraps a value in a fixed ±constant interval
- **THEN** the interval is marked nominal/unmeasured, not asserted at a measured
  `interval_level`

#### Scenario: Count-valued prediction
- **WHEN** a heuristic wraps an unbounded count (e.g. an expected bystander burden)
- **THEN** it does not assert an 80% (or other) measured coverage band around the count
