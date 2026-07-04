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

### Requirement: Out-of-distribution predictions widen, never narrow

When a prediction is flagged `in_distribution = False`, its interval SHALL be at least as
wide as the in-distribution interval it would otherwise have produced (widened, or its
`method` demoted), so an out-of-distribution input can never present a narrow, confident
interval even when model members happen to agree.

#### Scenario: Agreeing members on an OOD input
- **WHEN** ensemble members agree closely but the input is out of distribution
- **THEN** the returned interval is widened rather than narrow, and `calibrated = False`

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
