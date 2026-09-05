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

### Requirement: Benchmark results embed the full resolved config snapshot

A `BenchmarkResult` is a top-level result embedding provenance, so its `config_snapshot`
SHALL be the full resolved settings (minus volatile paths) drawn from `Settings.snapshot()`,
not a hand-built subset — identically to the design path. In particular it SHALL record
`interval_level`, which governs the predictive intervals and therefore the calibration
metric the leaderboard ranks on, so two results are comparable only when their governing
settings are visible.

#### Scenario: Benchmark config snapshot is complete
- **WHEN** a benchmark result is produced
- **THEN** its `config_snapshot` reflects the full resolved settings, including
  `interval_level`, not a two-key `{task, split_version}` subset

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

#### Scenario: Batch run records the governing seed, not the singleton default
- **WHEN** a cohort/batch run is given a non-default seed via `settings=` (e.g. CLI
  `af batch --seed …` or the web `/api/batch`)
- **THEN** the run-level provenance records that seed — the one threaded into every
  per-item `design()` call — rather than the process-singleton default, so the run header
  agrees with the per-item menus it summarizes and with what `af design` records for the
  same seed

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

#### Scenario: Config file governs a web run
- **WHEN** a user sets a value in the config file and starts the web API with no explicit
  settings (the module-level `create_app()`)
- **THEN** the app resolves settings through `Settings.load()` so that value governs the
  run and appears in provenance — a bare `Settings()` that reads env but skips the file
  does not satisfy the contract

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
- **THEN** each uses a unique temp file (a per-write token, not the payload object's
  identity, so writers of the same key never collide) and the final replace is atomic; a
  reader never sees a torn value

#### Scenario: Concurrent verified writes
- **WHEN** a `verify=True` cache is written and read concurrently under the same key
- **THEN** the checksum sidecar is published before the payload, so a concurrent reader
  never sees a payload without its sidecar and the fail-closed check raises only on genuine
  tampering, never on an in-progress write

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

### Requirement: Published schemas match the code

The JSON Schema files under `docs/schemas/` are the machine-readable contract the
project publishes, consumed by people who never read the Python. They SHALL be a
current export of the models: a test SHALL fail when any committed schema falls
behind, naming the stale files and the command that regenerates them.

#### Scenario: A model gains a field
- **WHEN** an exported model changes and the committed schemas are not regenerated
- **THEN** the schema-freshness test fails and names the stale files

### Requirement: Every model that produced a number is named

A menu's provenance SHALL record a card-backed checkpoint for **every** model that
produced a number in it, for every eligible chemistry — the efficiency scorer and
the outcome predictor alike, since the outcome model's intended probability feeds
the ranking's cleanliness objective. When the caller overrides a scorer, the
override's own card SHALL be recorded rather than the default it replaced;
otherwise a re-run from the stamped provenance reproduces different numbers.

#### Scenario: Default prime run
- **WHEN** the prime vertical runs with its defaults
- **THEN** provenance names both `pridict2-baseline` and `prime-outcome-baseline`

#### Scenario: Overridden scorer
- **WHEN** a chemistry's scorer is overridden through `design`
- **THEN** provenance names the override's card and not the default's

### Requirement: A run names every data source it consumed

A menu's provenance SHALL record a descriptor for every dataset the run read,
including a haplotype panel and a patient variant set, not only the reference,
gnomAD and ClinVar. A user-supplied file has no upstream version string, so it
SHALL be pinned by the content hash of what it contained — two runs agree iff the
bytes did. A source carrying no descriptor SHALL be omitted rather than given an
invented one.

Personal variants are the exception to content-hashing: the run SHALL record that
it was personalized and over how many variants, and SHALL NOT embed a fingerprint
of the file, which reproducibility does not require and which would put an
identifier for someone's genotypes into a shareable report.

#### Scenario: A haplotype-aware run
- **WHEN** a design consumes a haplotype panel
- **THEN** its provenance names the panel and its content pin

#### Scenario: A restricted off-target scan
- **WHEN** the off-target search is restricted to a set of intervals
- **THEN** the config snapshot records how many, how many bases they cover, and a
  content pin of the canonicalized list — so a restricted result is distinguishable
  from a genome-wide one, which reports far more sites for the same guide
- **AND** an unrestricted scan records `null` rather than an empty summary

#### Scenario: A personalized run
- **WHEN** a design consumes personal variants
- **THEN** its provenance records that fact and the variant count, with no content
  hash of the source

### Requirement: The rendered provenance footer accounts for every provenance field

Embedding the block is not enough — a reader audits the *render*, not the model. Every
human-facing render SHALL print the provenance facts from one shared source, so the HTML
and PDF cannot disagree, and every field of `Provenance` SHALL be either printed or
recorded as a deliberate omission with its reason.

#### Scenario: Datasets are named alongside models
- **WHEN** a report is rendered from a run that used a dataset (e.g. a gnomAD release)
- **THEN** the footer names the dataset and its version, not only the models — a result
  that names the code but not the data does not support a claim about the data

#### Scenario: A new provenance field
- **WHEN** a field is added to `Provenance`
- **THEN** it is either rendered in the footer or listed as omitted with a reason; it
  cannot be dropped silently
