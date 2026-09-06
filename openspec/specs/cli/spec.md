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
manifest, and isolate per-item failures so one bad variant does not abort the cohort. It
SHALL honor every whitelisted run-parameter config key it accepts — including `chemistry`
and `cell_context` — so a config restriction is not silently dropped for a cohort while the
same config governs `design`, the web `/api/batch`, and `design_many`.

#### Scenario: Resume
- **WHEN** `batch` re-runs against an existing manifest
- **THEN** already-recorded items are skipped and the run continues

#### Scenario: Batch honors chemistry and cell_context from config
- **WHEN** a `batch` config file sets `chemistry` (a chemistry restriction) or `cell_context`
- **THEN** the run restricts to those chemistries and records the cell context in each menu's provenance —
  it does not silently ignore a whitelisted key, matching `design`/web/`design_many`

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

### Requirement: A standalone off-target report says whose specificity it is

The `offtarget` command SHALL accept the spacer's own locus and exclude it from the
report when given. When it is not given, the guide's own perfect match is reported
like any other site — the honest answer to the question actually asked, since the
tool cannot know which perfect match is intended — and the command SHALL say so, so
its specificity is not read as the quantity a design report prints under the same
name. A malformed locus SHALL be a usage error, never a silently skipped exclusion.

#### Scenario: No locus given
- **WHEN** `offtarget` runs without the spacer's locus
- **THEN** the report records that the on-target was not excluded and the human line
  says so

#### Scenario: Locus given
- **WHEN** the locus is supplied
- **THEN** that one site is dropped and the report records the exclusion, so a
  spotless guide reads as spotless

#### Scenario: Malformed locus
- **WHEN** the locus is not `chrom:start-end(strand)`, or is empty
- **THEN** the command exits with a usage error rather than searching without it

### Requirement: The population-aware search is reachable from the CLI

Population-aware off-target nomination is the capability this tool exists for, so
the population allele source SHALL be supplyable from every command that searches —
`design`, `batch`, and `offtarget`. When ancestry labels are requested **without**
one, the command SHALL say that the scan was reference-only and that the empty
ancestry breakdown means "not measured", not "clean". An unreadable source SHALL be
a data error, never a silent fall back to a reference-only scan the caller believes
is population-aware.

#### Scenario: Ancestries requested without a population source
- **WHEN** `--populations` is given and **neither** a population-frequency source
  nor a haplotype panel is
- **THEN** the command warns that the scan is reference-only and the breakdown is
  unmeasured — and it does **not** warn when either source was supplied

#### Scenario: Population source supplied
- **WHEN** a population source is supplied and an allele creates a de-novo PAM
- **THEN** the site is nominated with `population` origin and an ancestry breakdown

#### Scenario: Unreadable population source
- **WHEN** any population, haplotype, or patient source cannot be read
- **THEN** the command exits with a data error

#### Scenario: Haplotype panel supplied
- **WHEN** a phased common-haplotype panel is supplied
- **THEN** the haplotype-aware pass runs and nominates a site that exists only on a
  co-inherited combination of alleles

#### Scenario: Personal variants supplied
- **WHEN** a patient's own variants are supplied
- **THEN** a site present in that genome but not the reference is nominated with
  `patient` origin

### Requirement: A region panel is validated against the reference

A region panel is usually a file made elsewhere, so naming a contig the reference does
not have is an ordinary mistake. It SHALL produce a usage error naming the region, the
contig and what the reference holds — never an unhandled traceback — because silently
dropping the region would search less than was asked for, and a smaller search reports
fewer off-targets.

A region running past a contig end SHALL NOT be refused: it is legitimate scoping, and
the report's searchable-fraction line already states how little of it held sequence.

#### Scenario: A panel from another assembly
- **WHEN** a BED names a contig absent from the reference
- **THEN** the command exits with a usage error naming it, and no traceback is shown

#### Scenario: A region past a contig end
- **WHEN** a region begins beyond the end of its contig
- **THEN** the search runs and reports that none of those bases were searchable
