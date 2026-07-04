# benchmark-harness (delta)

## MODIFIED Requirements

### Requirement: Splits are immutable and self-verifying

A split SHALL recompute both its membership hash and the dataset content hash on load and
raise on any mismatch; the dataset content hash SHALL cover only `(example_id, inputs,
label)`. Loading SHALL ALSO enforce that `train`, `val`, and `test` are pairwise disjoint
(no example appears in two folds) and that every split id exists in the dataset, raising an
integrity error otherwise — so leakage and dangling ids are structurally impossible, not
merely unlikely.

#### Scenario: Overlapping folds
- **WHEN** a split places the same example id in both train and test
- **THEN** loading it raises an integrity error

#### Scenario: Dangling id
- **WHEN** a split references an id absent from the dataset
- **THEN** loading it raises an integrity error, not a later `KeyError`

## ADDED Requirements

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
