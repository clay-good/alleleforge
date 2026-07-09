# benchmark-harness Specification

## Purpose

Score any scorer against a frozen `(task, split)` pair and emit a signed,
content-addressed, provenance-stamped result that a later editor cannot silently alter —
the reproducible, tamper-evident evaluation substrate ("CRISPR-Bench") that makes a
leaderboard trustworthy.

## Requirements

### Requirement: A fixed set of canonical tasks

The harness SHALL define the canonical tasks — Cas9 efficiency, Cas9 outcome,
base-edit outcome, prime-edit efficiency, and off-target classification — each binding a
dataset, an input key, a task kind, and a metric tuple with the ranking metric first.

#### Scenario: Primary metric
- **WHEN** a task is scored
- **THEN** its first metric is used as the ranking metric

### Requirement: Calibration is reported on every task

Calibration (`ece`) SHALL be reported on every task regardless of kind — interval
coverage for regression, binned reliability for classification, predicted-mode
reliability for distributions — always under the same key so calibration is comparable.
The metric SHALL distinguish **undefined** calibration — too few scorable predictions to
estimate reliability — from **perfect** calibration: an undefined ECE SHALL be surfaced as
undefined (null / `n/a`), not `0.0`, and SHALL be excluded from (sorted last on) the
leaderboard calibration tie-break, so a model that emits no real prediction cannot earn a
perfect honesty score or win the tie-break.

#### Scenario: Calibration always present
- **WHEN** any task result is produced
- **THEN** it carries an `ece` calibration number

#### Scenario: Degenerate scorer
- **WHEN** a scorer emits an empty distribution for every example, yielding no scorable
  confidence pairs
- **THEN** its calibration is reported as undefined, not `0.0`, and it does not out-rank an
  honestly-calibrated competitor on the calibration tie-break

### Requirement: Scorer outputs are contract-checked

Every scorer output SHALL be contract-checked as a `Prediction` (never a bare float),
attributed to the scorer by name.

#### Scenario: Bare float rejected
- **WHEN** a scorer returns a bare float during benchmarking
- **THEN** the harness raises, naming the offending scorer

### Requirement: Metrics treat non-finite inputs as degenerate

Every ranking/correlation/calibration metric SHALL treat a non-finite input value — `NaN`
**or** `±inf` — as degenerate and return the degenerate result (`0.0`, or `null` for an
undefined ECE), never a **perfect** score and never a non-JSON-serializable `NaN` or a
crash. A `NaN` slips every `<= 0` / `==` guard, and an `inf` sorts as the largest value and
satisfies those guards too, so both would otherwise let a corrupt or overflowing prediction
top the leaderboard.

#### Scenario: Infinite score is not perfect
- **WHEN** a scorer emits an `inf` (or `NaN`) point estimate that reaches a metric
- **THEN** `spearman`/`pearson`/`roc_auc`/`pr_auc` return the degenerate `0.0` and
  `expected_calibration_error` returns undefined — the corrupt prediction never scores as
  perfect, the result stays JSON-serializable, and no metric crashes

A `BenchmarkResult`'s `primary_value` and metric values are a signed *claim*, not a fresh
computation, so a non-finite one SHALL be rejected at construction/deserialization (not made
degenerate) — the leaderboard sorts on `primary_value`, and a `NaN` there loses every
comparison and would make the whole ranking order non-deterministic.

#### Scenario: Signed non-finite result rejected
- **WHEN** a `BenchmarkResult` is constructed or deserialized with a non-finite
  `primary_value` or metric value (e.g. an external submission signing `NaN`)
- **THEN** validation raises, so a submitter cannot scramble the leaderboard's deterministic
  order with a non-finite headline number

### Requirement: Results are signed and verifiable

A benchmark result SHALL carry a SHA-256 signature over its own canonical JSON body minus
the signature field, verifiable after the fact; editing a signed result SHALL invalidate
its signature.

#### Scenario: Tampered result
- **WHEN** a signed result is edited after signing
- **THEN** signature verification fails and it is rejected from the leaderboard

### Requirement: Results carry a portable reproducibility digest

A benchmark result SHALL carry a reproducibility digest computed over only its scientific
body — metrics rounded to a fixed precision, model-card facts, task name, split identity,
and dataset content hash — excluding wall-clock timestamp, package version, and local
config paths. Two independent runs of the same model on the same frozen `(task, split)`
SHALL produce the identical digest across AlleleForge releases and platforms. This digest
is distinct from the tamper signature (which seals the stored body verbatim).

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

### Requirement: Splits are immutable and self-verifying

A split SHALL recompute both its membership hash and the dataset content hash on load and
raise on any mismatch; the dataset content hash SHALL cover only `(example_id, inputs,
label)` so re-pinning a citation does not invalidate a split. Loading SHALL ALSO enforce
that `train`, `val`, and `test` are pairwise disjoint (no example appears in two folds)
and that every split id exists in the dataset, raising an integrity error otherwise — so
leakage and dangling ids are structurally impossible, not merely unlikely.

#### Scenario: Data changed
- **WHEN** the underlying fixture data changes
- **THEN** loading the split raises an integrity error

#### Scenario: Overlapping folds
- **WHEN** a split places the same example id in both train and test
- **THEN** loading it raises an integrity error

#### Scenario: Dangling id
- **WHEN** a split references an id absent from the dataset
- **THEN** loading it raises an integrity error, not a later `KeyError`

### Requirement: Results and submissions are versioned and unique

A benchmark result SHALL carry a schema/format version so downstream consumers can detect
drift when a field is added or reordered, and a submission SHALL contain at most one result
per `(model, task)` pair.

#### Scenario: Schema version present
- **WHEN** a benchmark result is serialized
- **THEN** it carries a schema version

#### Scenario: Duplicate task result
- **WHEN** a submission contains two results for the same `(model, task)`
- **THEN** it is rejected

### Requirement: The leaderboard admits only complete, verified submissions

The leaderboard SHALL admit only submissions carrying a complete model card (name,
license, citation) whose every result passes signature verification and whose result
model matches the submission; rankings SHALL respect each metric's direction with
deterministic tie-breaks.

#### Scenario: Missing license
- **WHEN** a submission omits a license
- **THEN** it is rejected before any entry is created

### Requirement: The generalization gap is orientation-corrected

The reported generalization gap SHALL be orientation-corrected so a positive value always
means worse held-out performance, regardless of whether the metric is ascending or
descending.

#### Scenario: Descending metric
- **WHEN** the gap is computed for a higher-is-better metric
- **THEN** a positive gap still denotes worse held-out performance
