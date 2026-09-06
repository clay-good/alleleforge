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
**or** `±inf` — as degenerate and return the metric's **worst** value, never a **perfect**
score and never a non-JSON-serializable `NaN` or a crash. A `NaN` slips every `<= 0` / `==`
guard, and an `inf` sorts as the largest value and satisfies those guards too, so both would
otherwise let a corrupt or overflowing prediction top the leaderboard. The degenerate value
is direction-aware: for a higher-is-better metric (correlation, ROC/PR-AUC) the worst value
is `0.0` (and ECE returns `null`); for the lower-is-better distribution divergence
`kl_divergence`, `0.0` is *perfect*, so a non-finite mass SHALL instead return `+inf` (the
worst), which the finite-headline validator then rejects rather than crowns.

#### Scenario: Infinite score is not perfect
- **WHEN** a scorer emits an `inf` (or `NaN`) point estimate that reaches a metric
- **THEN** `spearman`/`pearson`/`roc_auc`/`pr_auc` return the degenerate `0.0` and
  `expected_calibration_error` returns undefined — the corrupt prediction never scores as
  perfect, the result stays JSON-serializable, and no metric crashes

#### Scenario: Non-finite distribution mass is worst, not perfect
- **WHEN** a distribution scorer emits a non-finite mass (`inf`/`NaN`) that reaches
  `kl_divergence`
- **THEN** it returns `+inf` — its worst value — not the `0.0` a `max(0.0, NaN)` collapse
  would produce, so a broken distribution scorer cannot top the lower-is-better leaderboard

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
its signature. The signed body SHALL be internally consistent: the seed recorded at the top
of provenance SHALL equal the seed in its `config_snapshot`, so a re-deriver reading either
reproduces the run that actually happened.

#### Scenario: Tampered result
- **WHEN** a signed result is edited after signing
- **THEN** signature verification fails and it is rejected from the leaderboard

#### Scenario: Seed is consistent within provenance
- **WHEN** a result is produced with a non-default seed
- **THEN** `provenance.seed` and `provenance.config_snapshot["seed"]` are equal — the signed body does not
  record two different seeds

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

#### Scenario: A metric whose direction is unknown
- **WHEN** a signed result ranks on a `primary_metric` the harness declares no direction
  for (`primary_metric` is a free-form string, so a submitter may send any)
- **THEN** the submission is rejected, naming the metrics whose direction is known —
  the board never assumes higher wins, which would order the worst model first and
  print a confident arrow beside it

### Requirement: A rank never crosses a comparison group

A leaderboard rank SHALL be computed only within a comparison group — the
`(primary_metric, split_version, dataset_is_synthetic)` triple a score was measured
under. Entries from different groups SHALL NOT be interleaved in one ordering, and a
rendered board SHALL present one ranked table per group, labelled with the group, plus
a note when a task spans more than one.

Labelling a row is not enough: showing the split version and a `(synthetic)` mark
beside a score leaves the rank column itself asserting an ordering across populations
that nothing measured.

#### Scenario: A synthetic score above a real one
- **WHEN** one model scores 0.91 on the synthetic stand-in and another 0.42 on a real
  corpus, for the same task
- **THEN** each is rank 1 of its own group, and neither is ranked above the other

#### Scenario: Two metrics for one task
- **WHEN** two submissions for a task name different primary metrics
- **THEN** each metric heads its own table, sorted by its own direction, rather than
  one column labelled with the first submission's metric

### Requirement: The generalization gap is orientation-corrected

The reported generalization gap SHALL be orientation-corrected so a positive value always
means worse held-out performance, regardless of whether the metric is ascending or
descending.

#### Scenario: Descending metric
- **WHEN** the gap is computed for a higher-is-better metric
- **THEN** a positive gap still denotes worse held-out performance

### Requirement: A degenerate evaluation cannot flatter itself

A metric computed over a degenerate input SHALL NOT report a value that would rank
better than a real evaluation. Metrics with a bounded worst value (correlation,
AUROC, accuracy) SHALL fail toward it. A metric in `LOWER_IS_BETTER` that is
unbounded above has no such value and SHALL be reported as undefined (`None`)
rather than as its optimum.

#### Scenario: Empty distribution evaluation
- **WHEN** a distribution task is evaluated over zero examples
- **THEN** `kl` is `None` — not `0.0`, which `LOWER_IS_BETTER` would rank first —
  matching `ece`, which is computed on the same empty inputs

#### Scenario: Non-empty evaluation
- **WHEN** the same task is evaluated over at least one example
- **THEN** `kl` is a finite number, so the two cases are distinguishable

### Requirement: The leaderboard reports each model's out-of-distribution share

A score alone puts a model that stood behind every prediction on the same row as one
that self-flagged most of them. Every leaderboard render SHALL show the share of the
scored test fold the model declared out-of-distribution, alongside the calibration
column that exists for the same reason.

An unmeasurable share SHALL render as `n/a`, never as `0%`: a model that scored nothing
must not appear to have stood behind everything.

The share SHALL NOT enter the ranking. Trading it against accuracy needs a defensible
exchange rate the project does not have, and a fabricated one would be a worse dishonesty
than the omission.

#### Scenario: A model that disclaimed most of its predictions
- **WHEN** a result reports a large out-of-distribution count against its test-fold size
- **THEN** the board shows that share, and the model's rank is unaffected by it

#### Scenario: Nothing scored
- **WHEN** the test-fold size is zero
- **THEN** the cell reads `n/a`

### Requirement: A number from a synthetic stand-in is labelled as one

The bundled fixtures are synthetic stand-ins shipped so the harness runs without the real
corpora. A metric computed on them measures the contract, not the model, and SHALL be
labelled wherever it appears: in the run output, on the signed result, and on the
leaderboard, so a stand-in is never ranked against a real result silently.

The flag SHALL live in the result's **scientific body** covered by the reproducibility
digest, not in its provenance: which corpus a metric came from is as scientific a fact as
which split, and two runs differing only in that are not the same result.

#### Scenario: Running against a bundled fixture
- **WHEN** a benchmark task runs on a dataset marked synthetic
- **THEN** the output says the number measures the contract rather than the model, and
  the signed result records it

#### Scenario: A board holding both kinds
- **WHEN** a leaderboard contains a synthetic-derived row
- **THEN** that row is visibly marked in every render

### Requirement: The reproducibility digest is verifiable and comparable

A digest nobody recomputes is a claim nobody checks. A result SHALL be able to re-derive
its own digest from its scientific body, so a wrongly computed digest is detectable — the
signature cannot detect one, because it covers the digest as one more field and certifies
only that it was not edited afterwards.

The comparison the digest exists for SHALL be available as an operation: given two
results, whether they are the same scientific result, with each digest re-derived first
and the differing fields named when they are not.

#### Scenario: The same run at a different wall clock
- **WHEN** the same model is run on the same frozen split at two different times
- **THEN** the results are reported as the same scientific result, although their
  signatures differ

#### Scenario: A re-signed result with an altered number
- **WHEN** a scientific field is edited and the result re-signed
- **THEN** the signature check passes and the digest check fails

### Requirement: How much a model disclaimed is part of the scientific result

The count of predictions a model self-flagged out-of-distribution SHALL be part of the
scientific body the reproducibility digest covers, alongside the test-fold size it is
a share of. A digest covering the denominator and not the numerator guarantees half a
fraction.

#### Scenario: Two runs disclaiming different amounts
- **WHEN** two results agree on task, split, dataset, model and metrics but one model
  disclaimed nine predictions in ten and the other disclaimed none
- **THEN** their reproducibility digests differ and `bench compare` reports them as
  not the same scientific result, naming the field that differs
