## ADDED Requirements

### Requirement: Insertions validate their anchor before re-anchoring

For an anchored insertion, `resolve` SHALL validate the caller's asserted anchor/flanking
base against the reference **before** left-alignment re-anchors it from the reference, and
SHALL raise a reference-mismatch `ValueError` when the asserted anchor disagrees — so
left-alignment can never erase a wrong-build signal by replacing the asserted anchor with a
freshly-read reference base. This closes the insertion case in the existing "reference
mismatches fail closed" guarantee.

#### Scenario: Wrong-build insertion
- **WHEN** an insertion `chr1:100 A>AT` is resolved against a reference that carries `G` at
  position 100
- **THEN** resolution raises a reference-mismatch error, rather than silently re-anchoring to
  `G>GT`

#### Scenario: Correct insertion
- **WHEN** an insertion's asserted anchor matches the reference
- **THEN** it left-aligns and resolves normally

### Requirement: Source-database assembly is reconciled, not overwritten

When a variant originates from a database lookup, `resolve` SHALL NOT overwrite its build
with the requested `build` unconditionally. It SHALL raise when the requested build
disagrees with the source record's recorded native assembly, unless an explicit liftover is
performed, and provenance SHALL reflect the true source build.

#### Scenario: Mismatched database assembly
- **WHEN** a GRCh37 ClinVar or dbSNP record is resolved with `build="hg38"` and no liftover
- **THEN** resolution raises, rather than relabeling the variant as hg38

#### Scenario: Matching database assembly
- **WHEN** the requested build matches the source record's native assembly
- **THEN** the variant resolves and provenance records that assembly
