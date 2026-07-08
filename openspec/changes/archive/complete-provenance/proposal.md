# Complete and enforce provenance so results are actually re-derivable

## Why

"Reproducible to the byte" (principle 5) says a result must be re-derivable from its
provenance block. Today the block is partly decorative:

- **Datasets and tools are silently empty in the design path.** `Provenance` defaults them
  to `()` and the designer populates only `models` (`design/designer.py:242-255`), even
  though a run consumes a reference genome and ClinVar. The capture helpers exist
  (`genome/reference.py:71`, `data/registry.py:61`) but are never wired in, so a menu's
  provenance under-reports its own inputs.
- **The recorded seed drives no RNG in the design path.** The only real RNG is in
  `benchmark/calibration.py:97`, which uses its own module seed, not `cfg.seed`.
  Determinism today comes from the stub embedder and deterministic ranking, so
  `provenance.seed` is effectively decorative for design.
- **`config_snapshot` is a hand-built subset**, not the resolved `Settings`
  (`design/designer.py:248-254`), so it can drift from what actually governed the run.
- **The CLI ignores the config file.** It constructs `Settings(seed=...)` directly
  (`cli/main.py:299, 519`) instead of `Settings.load()`, so a user's `config.toml`
  (`maf_threshold`, `interval_level`, `cache_dir`) is not honored — the documented
  precedence is violated for the primary interface. Both the CLI and the web layer also
  hard-code `build="hg38"` (`cli/main.py:116`, `web/api/app.py:72, 131`) regardless of the
  user's `--reference`/`build`.

## What Changes

- **Auto-collect `tools` and `datasets`** into every result's provenance (reference build,
  ClinVar/gnomAD versions) the same way models are collected, so no result under-reports
  its inputs.
- **Thread `cfg.seed` into a single run-scoped RNG** that every stochastic step draws
  from, making the recorded seed load-bearing.
- **Snapshot the full resolved `Settings`** (minus volatile paths) into `config_snapshot`.
- **Route the CLI and web through `Settings.load()`** so the config file applies, and honor
  the user-supplied reference build instead of hard-coding hg38.
- Add an **`aforge verify <result>`** command that re-hashes the pinned checkpoints and
  datasets in a provenance block and re-runs a reproduce-style determinism check against
  the embedded config — turning provenance from a record into a checkable contract.

## Status (partial)

Task 1 has shipped: the design path now wires the existing dataset-capture helper
into provenance via `_collect_datasets`, so a menu's `Provenance.datasets` records
the reference build's `DatasetVersion` (and gnomAD/ClinVar once those classes carry
a version descriptor) instead of silently defaulting to empty. Task 3 has also
shipped: `config_snapshot` now embeds the full resolved `Settings` (via
`Settings.snapshot()`, minus the volatile `cache_dir`) alongside the run
parameters, so it reflects what actually governed the run rather than a hand-built
subset that can drift. Task 5 has also shipped: `aforge verify <result>` checks a
result's provenance is complete and self-consistent and, given `--cache-dir`,
re-hashes each pinned model checkpoint against the hash recorded in provenance,
exiting non-zero on incomplete provenance or a mismatch — turning provenance from a
record into a checkable contract. Task 4 has largely shipped: the CLI now routes its
settings through `Settings.load(config_file=config, seed=…)`, so a `config.toml`
key like `maf_threshold` is honored (and appears in the recorded settings snapshot)
instead of being ignored, and `--reference` labels the loaded genome and provenance
instead of a hard-coded `hg38`. Task 2 has now shipped: `Settings.rng()` is the single
run-scoped RNG (`random.Random(seed)`) that stochastic steps draw from, and the run's
one genuine stochastic step — the conformal-recalibration demo — now draws from it
instead of a private duplicate seed, so the recorded seed is load-bearing (its callers
thread `get_settings().rng()`). The design path still has no stochastic step, so nothing
there draws from the RNG yet; the seam is in place for the first one that does. Still
open: the reproduce-style determinism re-run inside `verify` (needs the original
reference, a follow-up). The warn-on-unknown-key
mode (task 4.3) has shipped: `_load_config` warns on any config key that is neither a
`Settings` field nor a recognized run-param knob, so a typo is surfaced rather than
silently ignored.

## Impact

- Specs: `provenance-reproducibility` (MODIFIED to require complete provenance,
  load-bearing seed, full config snapshot, and honored precedence; ADDED a verify
  command), `cli` (ADDED the verify subcommand and config-file honoring).
- Code: `types/provenance.py`, `design/designer.py`, `config.py`, `cli/main.py`,
  `web/api/app.py`, and a new verify entry point.
- Tests: a design menu's provenance lists its reference and dataset versions; the seed
  changes a stochastic step; a `config.toml` value governs a CLI run; `aforge verify`
  passes on a good result and fails on a tampered one.
