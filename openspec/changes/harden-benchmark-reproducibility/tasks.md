# Tasks

## 1. Reproducibility digest

- [ ] Add a canonical "scientific body" for a `BenchmarkResult` — metrics rounded to a fixed
  precision, model-card facts, task, split identity, dataset content hash — excluding
  timestamp, `alleleforge_version`, and local config paths.
- [ ] Compute a reproducibility digest over it (reuse `scripts/reproduce.py`'s
  canonicalization / float rounding) alongside the existing tamper signature.
- [ ] Test: the same model on the same `(task, split)` yields an identical digest across a
  simulated version bump and with the timestamp fixed or absent.

## 2. Full config snapshot for benchmark results

- [ ] In `run_benchmark`, populate `config_snapshot` from `Settings.snapshot()` instead of
  the hand-built `{"task", "split_version"}` subset.
- [ ] Test: a `BenchmarkResult`'s `config_snapshot` includes `interval_level` and the other
  resolved settings that governed its metrics.

## 3. Bind the split membership hash

- [ ] Include `split.split_sha256` in the signed benchmark body.
- [ ] Test: re-cutting a `v1` split over the same rows changes the bound hash, so a consumer
  can detect a moved fold.

## 4. Undefined vs perfect calibration

- [ ] Make ECE return/report "undefined" (null/`n/a`) when there are too few scorable
  predictions to estimate reliability, distinct from `0.0`.
- [ ] Exclude an undefined ECE from — or penalize it in — the leaderboard calibration
  tie-break, so a degenerate model cannot win the honesty axis.
- [ ] Test: a scorer that emits an empty distribution for every example reports undefined
  ECE and does not out-rank an honestly-calibrated competitor.
