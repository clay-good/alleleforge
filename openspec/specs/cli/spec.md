# cli Specification

## Purpose

Provide `aforge`: a thin, reproducible, config-driven command surface over the library
that carries no business logic, emits machine-readable JSON for every command, and reports
meaningful exit codes. The library is the source of truth; the CLI is a shell.

## Requirements

### Requirement: A stable subcommand surface with meaningful exit codes

The CLI SHALL expose `resolve`, `design`, `batch`, `offtarget`, and the `data` and `bench`
sub-apps, and SHALL use distinct exit codes: `0` success, `2` usage, `3` missing data,
`4` unavailable dependency.

#### Scenario: Missing dependency
- **WHEN** `batch` is given a VCF but the VCF backend is not installed
- **THEN** it exits with the unavailable-dependency code (4)

#### Scenario: Usage error
- **WHEN** a variant fails to resolve
- **THEN** stderr shows the error and it exits with the usage code (2)

### Requirement: Reproducible, machine-readable runs

Every command SHALL accept a global `--seed` (default `20240501`), `--reference`,
`--cache-dir`, and `--verbose`, and every structured-output command SHALL support `--json`
emitting stable, indented JSON. The CLI SHALL resolve settings through `Settings.load()`
so the user's config file is honored (not only the seed), and SHALL resolve a variant at
the user-supplied reference build rather than a hard-coded one. A supplied `--cache-dir`
SHALL actually redirect the cache root that the dataset registry, model loader, FM-index,
and reference index consume via the settings singleton — not merely be accepted and ignored.

#### Scenario: JSON output
- **WHEN** `design` is run with `--format json`
- **THEN** the ranked menu is printed as JSON to stdout and it exits `0`

#### Scenario: Cache directory honored
- **WHEN** a command is run with `--cache-dir <dir>`
- **THEN** the resolved settings' cache root is `<dir>`, so every cache consumer reads and
  writes there rather than the XDG default

#### Scenario: Config file honored
- **WHEN** a user's config file sets `maf_threshold` and a CLI command runs
- **THEN** the run uses that value

#### Scenario: Non-hg38 reference
- **WHEN** a non-hg38 reference is supplied
- **THEN** resolution uses that build, not a hard-coded `hg38`

### Requirement: Design requires a reference and validates output format

`design` SHALL require a reference FASTA (exiting missing-data if absent), SHALL support
output formats `json|tsv|html|pdf`, and SHALL require `--out` for `html`/`pdf` (else exit
usage); when `--out` is given it SHALL write the rendered bytes plus a `.provenance.json`
sidecar.

#### Scenario: PDF without output path
- **WHEN** `--format pdf` is given without `--out`
- **THEN** it exits with the usage code and reports the error

#### Scenario: Provenance sidecar
- **WHEN** `design --out report.html` runs
- **THEN** a `report.html.provenance.json` sidecar is written alongside it

### Requirement: Batch is streaming, resumable, and failure-isolating

`batch` SHALL stream a VCF or one-variant-per-line list, be resumable through a JSONL
manifest, and isolate per-item failures so one bad variant does not abort the cohort.

#### Scenario: Resume
- **WHEN** `batch` re-runs against an existing manifest
- **THEN** already-recorded items are skipped and the run continues

### Requirement: Trained-model opt-ins are explicit

Trained-model flags (`--trained-efficiency`, `--trained-outcome`,
`--trained-base-outcome`) SHALL each pass consent into a gated adapter only when set, so
the default run stays weight-free.

#### Scenario: No trained flag
- **WHEN** `design` runs without any trained-model flag
- **THEN** only weight-free heuristic scorers are used

### Requirement: A verify subcommand checks provenance

The CLI SHALL expose `aforge verify <result>` that re-hashes the pinned checkpoints and
datasets in the result's provenance and re-runs a determinism check against the embedded
config, exiting non-zero on any mismatch.

#### Scenario: Tampered artifact
- **WHEN** `aforge verify` is run on a result whose recorded artifact no longer matches its
  hash
- **THEN** it exits non-zero and names the mismatch
