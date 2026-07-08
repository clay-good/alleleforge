## ADDED Requirements

### Requirement: Results carry a portable reproducibility digest

A benchmark result SHALL carry a reproducibility digest computed over only its scientific
body — metrics rounded to a fixed precision, model-card facts, task name, split identity,
and dataset content hash — excluding wall-clock timestamp, package version, and local config
paths. Two independent runs of the same model on the same frozen `(task, split)` SHALL
produce the identical digest across AlleleForge releases and platforms. This digest is
distinct from the existing tamper signature (which seals the stored body verbatim).

#### Scenario: Same result across releases
- **WHEN** the same model is scored on the same `(task, split)` under two AlleleForge
  versions, at two wall-clock times
- **THEN** the reproducibility digest is identical, even though the tamper signature differs

#### Scenario: Different scientific result
- **WHEN** the model's metrics on the frozen split differ
- **THEN** the reproducibility digest differs

### Requirement: The signed result binds the split membership hash

The signed benchmark body SHALL include the split's `split_sha256` membership hash, so a
verifier can confirm a result was produced against the exact frozen fold membership, not
merely a version label string.

#### Scenario: Re-cut split is detectable
- **WHEN** a split labeled `v1` is re-cut over the same rows (changing fold membership)
- **THEN** the split hash bound into a new result differs from the prior result's, so a
  moved fold is distinguishable from a changed model

## MODIFIED Requirements

### Requirement: Calibration is reported on every task

Every benchmark task SHALL report a calibration metric (expected calibration error), and the
metric SHALL distinguish **undefined** calibration — too few scorable predictions to
estimate reliability — from **perfect** calibration. An undefined ECE SHALL be surfaced as
undefined (null/`n/a`), not as `0.0`, and SHALL be excluded from or penalized in leaderboard
ranking, so a model that emits no real prediction cannot earn a perfect honesty score or win
the calibration tie-break.

#### Scenario: Calibration reported
- **WHEN** a task produces scored predictions with confidences
- **THEN** an expected calibration error is reported for the task

#### Scenario: Degenerate scorer
- **WHEN** a scorer emits an empty distribution for every example, yielding no scorable
  confidence pairs
- **THEN** its calibration is reported as undefined, not `0.0`, and it does not out-rank an
  honestly-calibrated competitor on the calibration tie-break
