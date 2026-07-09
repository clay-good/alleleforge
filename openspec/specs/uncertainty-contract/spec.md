# uncertainty-contract Specification

## Purpose

Guarantee that every numeric efficiency or outcome prediction AlleleForge emits carries
honest, machine-checkable uncertainty — a point estimate, a calibrated predictive
interval, the method that produced it, and flags for calibration and in-distribution
status — so a confident wrong answer can never be mistaken for a confident right one.
This is design principle 2 ("honest uncertainty: no scorer returns a bare float") made
enforceable in the type system.

## Requirements

### Requirement: Predictions are never bare floats

Every numeric efficiency or outcome value the system returns SHALL be wrapped in a
`Prediction` carrying `value`, `interval`, `interval_level`, `method`,
`in_distribution`, and `calibrated`. The `Prediction` is immutable (frozen).

#### Scenario: A scorer returns a value
- **WHEN** any efficiency or outcome scorer produces a numeric result
- **THEN** it returns a `Prediction[float]`, not a `float`
- **AND** the `method` field records which `UncertaintyMethod` produced the interval

#### Scenario: A non-numeric payload
- **WHEN** the prediction payload is a structured outcome distribution rather than a scalar
- **THEN** the `Prediction[T]` still carries an interval, method, and honesty flags
- **AND** the point-containment check is skipped for the non-numeric payload

### Requirement: The interval is well-formed and contains the point

A `Prediction` SHALL reject construction unless `interval` is ordered (`low <= high`),
`interval_level` lies in `(0, 1]`, and — when `value` is numeric and not boolean — the
point estimate lies within `[low, high]`.

#### Scenario: Inverted interval
- **WHEN** a `Prediction` is constructed with `interval` low greater than high
- **THEN** construction raises `ValueError`

#### Scenario: Point outside interval
- **WHEN** a numeric `value` lies outside its `[low, high]` interval
- **THEN** construction raises `ValueError`

#### Scenario: Interval level out of range
- **WHEN** `interval_level` is `0`, negative, or greater than `1`
- **THEN** construction raises `ValueError`

### Requirement: Honesty flags carry defined meaning

`method`, `calibrated`, and `in_distribution` SHALL each carry a defined, auditable
meaning, and the flags SHALL be tamper-resistant, not honor-system:

- `calibrated = True` SHALL be settable only by a fitted calibrator (the conformal or
  isotonic path). A `Prediction` constructed directly by a scorer SHALL default to
  `calibrated = False`; a direct attempt to assert `calibrated = True` SHALL not be
  honored.
- A prediction produced without a real trained backbone (e.g. on the weight-free stub
  embedder) SHALL report `calibrated = False` and a heuristic-appropriate `method`, so a
  heuristic result is distinguishable from a trained one without reading provenance.
- `in_distribution = False` SHALL NOT coexist with `calibrated = True`.

`method` remains one of `ensemble`, `evidential`, `quantile`, `conformal`, `heuristic`,
`agreement`, or `none`, stored verbatim in provenance for audit.

#### Scenario: Scorer cannot self-declare calibration
- **WHEN** a scorer constructs a `Prediction` asserting `calibrated = True` without a
  fitted calibrator
- **THEN** the result reports `calibrated = False`

#### Scenario: Stub-backbone result is honest
- **WHEN** the default ensemble scorer runs on the weight-free stub embedder
- **THEN** the returned prediction reports `calibrated = False` and a heuristic method

#### Scenario: Out-of-distribution input
- **WHEN** an input falls outside the training reference region
- **THEN** the returned `Prediction` has `in_distribution = False`

#### Scenario: OOD cannot be calibrated
- **WHEN** a prediction has `in_distribution = False`
- **THEN** it also has `calibrated = False`

### Requirement: Calibration survives faithful round-trip but not forgery

The `calibrated` guarantee SHALL be enforced by gating the **raw input** to
construction, not by mutating a built `Prediction`. Because the model is frozen and may
be aliased (nested in a `RankedMenu`, revalidated), constructing a container around a
calibrated prediction SHALL NOT downgrade or mutate it. AlleleForge's own serialized
output SHALL be faithfully round-trippable: a calibrated prediction serializes with
`calibrated = true`, and re-loading it through the **trusted deserialization context**
(the sole path, besides the fitted-calibrator path, that carries the calibration token)
SHALL preserve `calibrated = True`. A plain load of untrusted JSON SHALL still coerce
`calibrated` to `False`, so a hand-crafted or tampered payload cannot forge calibration,
and the `in_distribution = False` guard SHALL hold through the trusted path as well.

#### Scenario: Nesting a calibrated prediction
- **WHEN** a calibrated `Prediction` is placed inside another model (e.g. a
  `DesignCandidate` in a `RankedMenu`)
- **THEN** the nested prediction still reports `calibrated = True`
- **AND** the original prediction instance is not mutated

#### Scenario: Trusted round-trip preserves calibration
- **WHEN** a serialized menu is re-loaded through the trusted deserialization context
- **THEN** a prediction serialized with `calibrated = true` loads back as `calibrated = True`

#### Scenario: Untrusted load cannot forge calibration
- **WHEN** arbitrary JSON asserting `calibrated = true` is loaded without the trusted context
- **THEN** the loaded prediction reports `calibrated = False`

#### Scenario: OOD cannot be calibrated even under trust
- **WHEN** JSON with `in_distribution = false` and `calibrated = true` is loaded through the
  trusted deserialization context
- **THEN** the loaded prediction reports `calibrated = False`

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

### Requirement: Interval repair is recorded, not silent

When packaging a value and interval requires widening the interval to contain the point
estimate (a signal the underlying head is inconsistent), the system SHALL record a note
rather than silently repairing it, so a broken head is surfaced for audit.

#### Scenario: Point outside its own interval
- **WHEN** a scorer's point estimate falls outside its predicted interval
- **THEN** the interval is widened to contain it AND a note recording the repair is
  attached for audit

### Requirement: Interval widens on ensemble disagreement

A deep ensemble (default 5 members) SHALL produce a predictive interval whose width
grows with member disagreement, so out-of-distribution inputs where members diverge
receive wider intervals. An ensemble requires at least one member.

#### Scenario: Members agree
- **WHEN** all ensemble members return near-identical values
- **THEN** the interval is narrow around their mean

#### Scenario: Members diverge
- **WHEN** ensemble members disagree sharply
- **THEN** the interval widens in proportion to the member standard deviation

#### Scenario: Empty ensemble
- **WHEN** a `DeepEnsemble` is constructed with no members
- **THEN** it raises `ValueError`

### Requirement: Post-hoc interval calibration carries a coverage guarantee

Split-conformal recalibration SHALL adjust predictive-interval width from a held-out
calibration set so recalibrated intervals achieve at least the requested marginal
coverage on exchangeable data, while preserving each example's relative interval shape
(a single multiplicative width scale). Recalibrated predictions carry `method =
conformal` and `calibrated = True`.

#### Scenario: Miscalibrated intervals are corrected
- **WHEN** a scorer's empirical coverage is measured off its nominal `interval_level` and
  a `ConformalCalibrator` is fit on held-out predictions and truths
- **THEN** recalibrated intervals achieve the target marginal coverage
- **AND** each recalibrated `Prediction` reports `method = conformal`, `calibrated = True`

#### Scenario: Degenerate calibration interval
- **WHEN** any calibration interval has non-positive width
- **THEN** `ConformalCalibrator.fit` raises `ValueError` directing the caller to widen it

### Requirement: Point-estimate calibration is monotonic

Isotonic post-hoc calibration SHALL fit a non-decreasing map from raw scores to
outcomes (pool-adjacent-violators), so calibration cannot reorder predictions, and
SHALL reduce expected calibration error on a miscalibrated set.

#### Scenario: Calibrating preserves ranking
- **WHEN** an `IsotonicCalibrator` is fit and applied to a set of scores
- **THEN** the calibrated values are non-decreasing in the raw scores

#### Scenario: Calibrator used before fitting
- **WHEN** `predict_one` is called on an unfitted calibrator
- **THEN** it raises `ValueError`

### Requirement: Out-of-distribution detection from a training reference

An OOD detector SHALL flag inputs whose nearest-neighbor distance to a stored training
reference (in embedding space) exceeds a threshold, derived by default from a quantile
of the reference's own nearest-neighbor distances. The reference set must be non-empty.

#### Scenario: In-distribution input
- **WHEN** an input embedding lies within the derived distance threshold of the reference
- **THEN** `is_in_distribution` returns `True`

#### Scenario: Far input
- **WHEN** an input embedding is farther than the threshold from every reference point
- **THEN** `is_in_distribution` returns `False`

### Requirement: Combining predictions preserves honesty

Combining independent numeric predictions SHALL require a non-empty input, a single
shared `interval_level`, and a known reduction (`mean` or `sum`). The combined result
carries `method = agreement`, and its `calibrated` and `in_distribution` flags are the
logical AND across inputs (the combination is no more calibrated or in-distribution than
its least-calibrated, least-in-distribution member).

#### Scenario: Averaging two calibrated in-distribution predictions
- **WHEN** two predictions with the same level, both calibrated and in-distribution, are
  combined with `reduce = "mean"`
- **THEN** the result averages the points and bounds, `method = agreement`, and stays
  `calibrated = True`, `in_distribution = True`

#### Scenario: One member is uncalibrated
- **WHEN** any combined member has `calibrated = False`
- **THEN** the combined prediction has `calibrated = False`

#### Scenario: Mixed interval levels
- **WHEN** the inputs do not share one `interval_level`
- **THEN** `combine` raises `ValueError`
