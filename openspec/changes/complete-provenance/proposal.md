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

## Impact

- Specs: `provenance-reproducibility` (MODIFIED to require complete provenance,
  load-bearing seed, full config snapshot, and honored precedence; ADDED a verify
  command), `cli` (ADDED the verify subcommand and config-file honoring).
- Code: `types/provenance.py`, `design/designer.py`, `config.py`, `cli/main.py`,
  `web/api/app.py`, and a new verify entry point.
- Tests: a design menu's provenance lists its reference and dataset versions; the seed
  changes a stochastic step; a `config.toml` value governs a CLI run; `aforge verify`
  passes on a good result and fails on a tampered one.
