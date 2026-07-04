# cli (delta)

## MODIFIED Requirements

### Requirement: Reproducible, machine-readable runs

Every command SHALL accept a global `--seed` (default `20240501`), `--reference`,
`--cache-dir`, and `--verbose`, and every structured-output command SHALL support `--json`
emitting stable, indented JSON. The CLI SHALL resolve settings through `Settings.load()`
so the user's config file is honored (not only the seed), and SHALL resolve a variant at
the user-supplied reference build rather than a hard-coded one.

#### Scenario: Config file honored
- **WHEN** a user's config file sets `maf_threshold` and a CLI command runs
- **THEN** the run uses that value

#### Scenario: Non-hg38 reference
- **WHEN** a non-hg38 reference is supplied
- **THEN** resolution uses that build, not a hard-coded `hg38`

## ADDED Requirements

### Requirement: A verify subcommand checks provenance

The CLI SHALL expose `aforge verify <result>` that re-hashes the pinned checkpoints and
datasets in the result's provenance and re-runs a determinism check against the embedded
config, exiting non-zero on any mismatch.

#### Scenario: Tampered artifact
- **WHEN** `aforge verify` is run on a result whose recorded artifact no longer matches its
  hash
- **THEN** it exits non-zero and names the mismatch
