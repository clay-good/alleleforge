# provenance-reproducibility (delta)

## MODIFIED Requirements

### Requirement: Every top-level result embeds provenance

Every top-level result SHALL embed a `Provenance` recording `alleleforge_version`,
`reference_build`, `seed`, `tools`, `datasets`, `models`, `config_snapshot`, and a
timezone-aware UTC `timestamp`, and the block SHALL be **complete for the run**: `tools`
and `datasets` SHALL be auto-collected (the reference build and every accessed dataset
version), not left empty, and `config_snapshot` SHALL be the full resolved settings
(minus volatile paths), not a hand-built subset. A naive timestamp SHALL be rejected.

#### Scenario: Design menu lists its data inputs
- **WHEN** a design menu is produced from a reference and a ClinVar/gnomAD lookup
- **THEN** its provenance `datasets` lists the reference build and those dataset versions,
  not an empty tuple

#### Scenario: Full config snapshot
- **WHEN** a result is produced
- **THEN** its `config_snapshot` reflects the full resolved settings that governed the run

### Requirement: The seed is fixed and recorded

The global seed SHALL default to `20240501`, be recorded in provenance, and SHALL seed a
single run-scoped RNG that every stochastic step draws from, so the recorded seed actually
determines any randomness rather than being decorative.

#### Scenario: Seed determines randomness
- **WHEN** a run includes a stochastic step and the seed is changed
- **THEN** the output changes, and re-running with the original seed reproduces it

### Requirement: Configuration resolves by a documented precedence

`Settings` SHALL be immutable and resolve later-wins in the order: field defaults → user
config file → `ALLELEFORGE_*` environment variables → explicit constructor arguments, and
**all interfaces (library, CLI, web) SHALL honor this precedence** by resolving settings
through `Settings.load()` — the config file SHALL apply to CLI and web runs, not only the
seed. `interval_level` and `maf_threshold` SHALL be validated to `[0, 1]`; network access
SHALL default off.

#### Scenario: Config file governs a CLI run
- **WHEN** a user sets `maf_threshold` in the config file and runs a CLI command
- **THEN** that value governs the run

## ADDED Requirements

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
