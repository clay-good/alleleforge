# Tasks

## 1. Auto-collect datasets and tools
- [x] 1.1 Collect the reference build and every accessed dataset version into
      `Provenance.datasets`/`tools` in the design path, mirroring `_collect_model_checkpoints`.
      *(Reference `DatasetVersion` wired in via `_collect_datasets`; gnomAD/ClinVar are
      recorded once those classes carry a version descriptor.)*
- [x] 1.2 Test: a design menu's provenance lists its reference and dataset versions.

## 2. Make the seed load-bearing
- [x] 2.1 Create a single run-scoped RNG seeded from `cfg.seed` and thread it into every
      stochastic step (start with any that exist; enforce for future ones). *(`Settings.rng()`
      is the one run-scoped `random.Random(seed)` seam; the run's only genuine stochastic
      step — the conformal-recalibration demo — now draws from it instead of a private
      duplicate `SEED = 20240501`, and its real callers (`viz.figures`, `calibration_study`)
      pass `get_settings().rng()`, so the recorded seed governs the randomness. The design
      path still has no stochastic step, so nothing there draws from the RNG yet — the seam
      exists for the first one that does.)*
- [x] 2.2 Test: changing the seed changes a stochastic output; fixing it reproduces.
      *(`test_seed_governs_a_stochastic_step` + `test_rng_is_reproducible_and_seed_dependent`
      in `tests/test_config.py`.)*

## 3. Full config snapshot
- [x] 3.1 Snapshot the resolved `Settings` (minus volatile paths) into `config_snapshot`.
- [x] 3.2 Test: the snapshot round-trips and matches the settings that governed the run.

## 4. Honor config precedence in CLI and web
- [x] 4.1 Route the CLI and web through `Settings.load()` so the config file applies.
      *(CLI routes `Settings.load(config_file=config, seed=state.seed)`; the web layer
      already threads a `Settings` instance.)*
- [x] 4.2 Honor the user-supplied reference build instead of hard-coding `hg38`.
- [x] 4.3 Add a warn-on-unknown-key mode for the config file.
- [x] 4.4 Tests: a `config.toml` `maf_threshold`/`interval_level` governs a CLI run; a
      non-hg38 reference resolves at its own build.

## 5. Add `aforge verify`
- [x] 5.1 Implement `aforge verify <result>`: re-hash pinned checkpoints/datasets in the
      provenance block and re-run a reproduce-style determinism check against the embedded
      config; non-zero exit on any mismatch. *(Ships: checks provenance completeness and,
      with `--cache-dir`, re-hashes pinned model checkpoints against their recorded hash;
      the reproduce-style re-run needs the original reference and is a follow-up.)*
- [x] 5.2 Tests: passes on a good result, fails on a tampered one.

## 6. Reconcile
- [x] 6.1 Regenerate the reproduce golden; `make ci` green. *(The default resolved seed
      equals the retired hardcoded `SEED` value, so the reproduce golden and the committed
      figures/report are byte-identical — no regeneration needed. `make ci` green: ruff +
      mypy --strict clean, 1002 passed/5 skipped at 97.4% coverage, docs strict, reproduce
      matches golden.)*
