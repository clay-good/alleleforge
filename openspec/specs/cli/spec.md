# cli Specification

## Purpose

Provide `aforge`: a thin, reproducible, config-driven command surface over the library
that carries no business logic, emits machine-readable JSON for every command, and reports
meaningful exit codes. The library is the source of truth; the CLI is a shell.

## Requirements

### Requirement: A stable subcommand surface with meaningful exit codes

The CLI SHALL expose `resolve`, `design`, `batch`, `offtarget`, `verify`, `lift`, and the
`data` and `bench` sub-apps, and SHALL use distinct exit codes: `0` success, `2` usage,
`3` missing data, `4` unavailable dependency.

#### Scenario: Missing dependency
- **WHEN** `batch` is given a VCF but the VCF backend is not installed
- **THEN** it exits with the unavailable-dependency code (4)

#### Scenario: Usage error
- **WHEN** a variant fails to resolve
- **THEN** stderr shows the error and it exits with the usage code (2)

### Requirement: A remedy for a build mismatch

`resolve` SHALL refuse a record whose native assembly disagrees with the requested build,
rather than relabelling coordinates that would then designate a different locus. Because a
refusal that names an operation the tool does not offer is not actionable, the CLI SHALL
provide `lift`, converting loci between assemblies through a caller-supplied UCSC chain
file, which is never downloaded.

`lift` SHALL print `input<TAB>output` per locus, in order, in the same `chrom:start-end`
form `--region` accepts, so its output pipes back in. An unmappable locus SHALL print
`UNMAPPED` rather than being dropped — a shorter list is a smaller search — and the
command SHALL exit non-zero when any locus is unmappable.

#### Scenario: A locus that lifts
- **WHEN** `lift chr1:100-200 --chain hg19ToHg38.over.chain --from hg19 --to hg38` maps
- **THEN** it prints the input and the lifted locus separated by a tab, and exits 0

#### Scenario: A locus that does not lift
- **WHEN** a locus has no mapping in the chain file
- **THEN** it prints `UNMAPPED` for that locus and exits non-zero

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

### Requirement: A malformed or unsupported input fails with a decision, not a traceback

Every file input SHALL fail with a message a user can act on, and with the exit code that
matches *why* it failed — these are different answers and the CLI already distinguishes
them:

- an input the reference cannot serve (an unknown contig): a usage error naming what is
  valid;
- a malformed file (a missing column): a usage error naming the missing element **and**
  the expected schema, since the next question is what it should have been;
- a feature that is not installed (an optional dependency): unavailable, not missing
  data — the file is fine.

#### Scenario: A panel with the wrong header
- **WHEN** a haplotype panel lacks a required column
- **THEN** the error names the column and the expected header, and no traceback is shown

#### Scenario: An optional dependency absent
- **WHEN** reading a VCF requires an extra that is not installed
- **THEN** the command exits unavailable and states how to install it

### Requirement: Every whitelisted config key is honored

The config loader warns on an unknown key, so a key inside the whitelist produces no
warning at all. A whitelisted key that no command reads would therefore be accepted
silently and do nothing, and the run would differ from the one the config describes.

Every key the loader accepts SHALL be read by the commands, and a run configured
entirely from a file SHALL produce the same result as the equivalent command-line flags.

#### Scenario: A run driven from a config file
- **WHEN** a design is run with its options in a config file rather than as flags
- **THEN** the candidates, the rationale and the provenance snapshot match the
  flag-driven run

### Requirement: A cohort's counts range over the same population

A run summary states how many items were processed, succeeded, failed and skipped. These
appear together and are read together, so they SHALL all count *this run's requested
items* — a skipped count taken from the manifest file describes a different population,
and the two cannot be added even though their presentation invites it.

The processed and skipped counts SHALL sum to the number of items requested, and the
human summary SHALL state that requested total rather than leading with the processed
count, which is zero for a resume with nothing outstanding.

#### Scenario: A manifest reused with a narrower list
- **WHEN** a run requests fewer items than the manifest records
- **THEN** the skipped count reflects only the requested items already recorded

### Requirement: A build mismatch has a remedy in the tool

When variant resolution refuses a record whose native assembly disagrees with the
requested build, the coordinate lift it instructs the caller to perform SHALL be
available as a CLI command. An instruction a user cannot act on is a dead end.

The command SHALL accept and emit loci in the same form `--region` accepts, so its
output can be handed straight back, and SHALL report an unmappable locus explicitly
and exit non-zero rather than omitting it — a shorter region list searches less than
was asked for and reports fewer off-targets.

#### Scenario: A locus that does not lift
- **WHEN** one of several loci has no mapping in the chain file
- **THEN** it is printed as `UNMAPPED`, the others are still printed, and the command
  exits non-zero

### Requirement: A missing optional dependency is reported, not raised

A command whose deferred imports need an optional extra SHALL report the missing
module and the extra that installs it, and exit non-zero. The heavy imports are
deferred into the command bodies, but the modules they pull in import their own
dependencies at module level, so the failure arrives before any explicit check.

#### Scenario: The documented CLI install, without the genome extra
- **WHEN** `aforge design` runs in an environment installed as `alleleforge[cli]`
- **THEN** it prints the missing dependency and `pip install 'alleleforge[genome]'`
  rather than a `ModuleNotFoundError` traceback

### Requirement: The cohort command offers the single-variant command's options

Every option `aforge design` accepts SHALL be accepted by `aforge batch`, except those
that shape a single rendered document, which the cohort path does not produce. A
cohort is where a trained model or a PAM-flexible fallback matters most, and an option
honoured only through a config file is invisible from `--help`.

#### Scenario: A cohort run with a trained model
- **WHEN** a user runs `aforge batch … --trained-efficiency`
- **THEN** the trained scorer is used for every item, as it is for `aforge design`

### Requirement: A cohort reports both completion and success

A cohort run SHALL complete every item and keep its manifest intact regardless of
per-item failures, and SHALL exit non-zero when any item failed. "The run completed"
and "the run succeeded" are different facts, and a caller driving the command can
observe only the exit code.

A cohort item that produced no candidates SHALL record why, in its summary, its
manifest entry and its exported row — the cohort is the one surface where a reader
cannot re-run the item by hand to find out.

#### Scenario: One item of many fails
- **WHEN** a cohort run has at least one failed item
- **THEN** every other item is still designed and recorded, and the command exits
  non-zero naming how many failed

### Requirement: A resume retries what failed and survives an interrupted write

Resuming a cohort SHALL skip only the items that succeeded. An item recorded as failed
did no work worth preserving, and skipping it makes a re-run of a partially failed cohort
report nothing to do and exit successfully — the reassuring direction, from a run that
examined none of the items the user re-ran it for.

Reading the manifest SHALL tolerate a truncated final line, which is what an interrupted
append leaves and precisely the state resume exists to recover from; the item it half
described simply runs again. A malformed line elsewhere SHALL be an error naming the
line, since silently skipping it would silently recompute or silently drop an item.

#### Scenario: Re-running a cohort that had failures
- **WHEN** a cohort with one success and one failure is run again with the same manifest
- **THEN** the successful item is skipped, the failed one is retried, and the run does
  not report itself as empty and clean

### Requirement: An empty search is not a successful exit

Where the off-target command examined no sequence at all, it SHALL emit its output,
including the statement that nothing was searched, and then exit non-zero with the
missing-data status. The numbers such a run prints — no sites, worst score zero,
specificity one — are the most reassuring the tool can produce, and a caller that
branches on the exit status has no other way to tell them apart from a real result.

The machine-readable payload SHALL carry the extent searched alongside the budgets and
cut-offs, since every number it reports is conditional on that extent and a zero there
makes the rest meaningless.

#### Scenario: A truncated reference
- **WHEN** the reference holds a contig with no bases
- **THEN** the command explains that nothing was searched and exits non-zero, and the
  JSON payload reports `searched_bases` as zero
