# provenance-reproducibility Specification

## Purpose

Make every top-level result self-contained and re-derivable: embed a `Provenance` block
recording versions, seed, datasets, models, and config; resolve configuration by a
documented precedence; content-address every cache; and prove byte-determinism with a
golden audit. This is design principle 5 ("reproducible to the byte").

## Requirements

### Requirement: Every top-level result embeds provenance

Every top-level result SHALL embed a `Provenance` recording `alleleforge_version`,
`reference_build`, `seed`, `tools`, `datasets`, `models`, `config_snapshot`, and a
timezone-aware UTC `timestamp`, and the block SHALL be **complete for the run**: `tools`
and `datasets` SHALL be auto-collected (the reference build and every accessed dataset
version), not left empty, and `config_snapshot` SHALL be the full resolved settings (minus
volatile paths), not a hand-built subset. A naive (non-tz-aware) timestamp SHALL be rejected.

#### Scenario: Design menu provenance
- **WHEN** a design menu is produced
- **THEN** its provenance carries the version, seed, reference build, per-chemistry model
  checkpoints, and a UTC timestamp

#### Scenario: Design menu lists its data inputs
- **WHEN** a design menu is produced from a reference and a ClinVar/gnomAD lookup
- **THEN** its provenance `datasets` lists the reference build and those dataset versions,
  not an empty tuple

#### Scenario: Full config snapshot
- **WHEN** a result is produced
- **THEN** its `config_snapshot` reflects the full resolved settings that governed the run

#### Scenario: Naive timestamp
- **WHEN** a provenance block is built with a non-tz-aware timestamp
- **THEN** construction raises `ValueError`

### Requirement: Model checkpoints carry their known failure modes

Each recorded `ModelCheckpoint` SHALL carry the card's `known_failure_modes` into
provenance so a result can be audited against known model weaknesses without reopening
the cards.

#### Scenario: Audit a design
- **WHEN** a consumer inspects a result's provenance
- **THEN** each model's documented failure modes are present in the block

### Requirement: The seed is fixed and recorded

The global seed SHALL default to the spec-fixed value `20240501`, be recorded in
provenance, and SHALL seed a single run-scoped RNG that every stochastic step draws from,
so the recorded seed actually determines any randomness rather than being decorative.

#### Scenario: Default seed recorded
- **WHEN** a run completes with no explicit seed override
- **THEN** provenance records seed `20240501`

#### Scenario: Seed determines randomness
- **WHEN** a run includes a stochastic step and the seed is changed
- **THEN** the output changes, and re-running with the original seed reproduces it

### Requirement: Configuration resolves by a documented precedence

`Settings` SHALL be immutable and resolve later-wins in the order: field defaults →
user config file → `ALLELEFORGE_*` environment variables → explicit constructor
arguments, and **all interfaces (library, CLI, web) SHALL honor this precedence** by
resolving settings through `Settings.load()` — the config file SHALL apply to CLI and web
runs, not only the seed. `interval_level` and `maf_threshold` SHALL be validated to
`[0, 1]`; network access SHALL default off so registries never auto-download without consent.

#### Scenario: Env overrides file
- **WHEN** both a config file and an `ALLELEFORGE_*` env var set the seed
- **THEN** the env var wins, and an explicit constructor argument wins over both

#### Scenario: Config file governs a CLI run
- **WHEN** a user sets `maf_threshold` in the config file and runs a CLI command
- **THEN** that value governs the run

#### Scenario: Out-of-range level
- **WHEN** `interval_level` is set to `1.5`
- **THEN** settings construction raises a validation error

### Requirement: Provenance is a checkable contract

The system SHALL provide a verification command that re-hashes the pinned checkpoints and
datasets recorded in a result's provenance and re-runs a determinism check against the
embedded config, exiting non-zero on any mismatch — turning provenance from a record into
a contract a reviewer can check.

#### Scenario: Verify a good result
- **WHEN** a result with complete provenance is verified and its artifacts are intact
- **THEN** verification passes

#### Scenario: Verify a tampered result
- **WHEN** a recorded checkpoint or dataset no longer matches its pinned hash
- **THEN** verification fails with a non-zero exit

### Requirement: Caches are content-addressed and atomically written

Cache keys SHALL be the SHA-256 of canonical JSON over a format version plus every
result-determining input; writes SHALL be atomic (unique temp then replace); a different
input SHALL always be a different key. The off-target cache SHALL be used only for a
reference-only, default-scorer search and SHALL bypass caching when any population,
haplotype, patient, or custom-scorer augmentation is present.

#### Scenario: Concurrent writers
- **WHEN** two processes write the same cache key at once
- **THEN** each uses a unique temp file and the final replace is atomic; a reader never
  sees a torn value

#### Scenario: Augmented search is not cached
- **WHEN** an off-target search adds populations, haplotypes, or a custom scorer
- **THEN** the result is computed fresh and never served from the reference-only cache

### Requirement: A golden audit proves determinism

`scripts/reproduce.py` SHALL re-derive the acceptance design menu twice, assert
byte-identical output, strip volatile keys, canonicalize, and diff a digest against a
committed golden, exiting non-zero on drift.

#### Scenario: Determinism drift
- **WHEN** any scientific field of the acceptance menu changes
- **THEN** the golden digest mismatches and the audit exits non-zero
