# Tasks

## 1. Auto-collect datasets and tools
- [ ] 1.1 Collect the reference build and every accessed dataset version into
      `Provenance.datasets`/`tools` in the design path, mirroring `_collect_model_checkpoints`.
- [ ] 1.2 Test: a design menu's provenance lists its reference and dataset versions.

## 2. Make the seed load-bearing
- [ ] 2.1 Create a single run-scoped RNG seeded from `cfg.seed` and thread it into every
      stochastic step (start with any that exist; enforce for future ones).
- [ ] 2.2 Test: changing the seed changes a stochastic output; fixing it reproduces.

## 3. Full config snapshot
- [ ] 3.1 Snapshot the resolved `Settings` (minus volatile paths) into `config_snapshot`.
- [ ] 3.2 Test: the snapshot round-trips and matches the settings that governed the run.

## 4. Honor config precedence in CLI and web
- [ ] 4.1 Route the CLI and web through `Settings.load()` so the config file applies.
- [ ] 4.2 Honor the user-supplied reference build instead of hard-coding `hg38`.
- [ ] 4.3 Add a warn-on-unknown-key mode for the config file.
- [ ] 4.4 Tests: a `config.toml` `maf_threshold`/`interval_level` governs a CLI run; a
      non-hg38 reference resolves at its own build.

## 5. Add `aforge verify`
- [ ] 5.1 Implement `aforge verify <result>`: re-hash pinned checkpoints/datasets in the
      provenance block and re-run a reproduce-style determinism check against the embedded
      config; non-zero exit on any mismatch.
- [ ] 5.2 Tests: passes on a good result, fails on a tampered one.

## 6. Reconcile
- [ ] 6.1 Regenerate the reproduce golden; `make ci` green.
