# Harden benchmark reproducibility and calibration honesty

## Why

A prior change (`guard-benchmark-integrity`, archived) enforced split disjointness and added
a result schema version. Four gaps remain that keep a published benchmark result from being
independently re-derivable — or let a degenerate model win the honesty axis. Notably,
`scripts/reproduce.py` already learned the right lessons for the *design* path; the
benchmark runner never inherited them:

1. **The signature seals volatile, non-portable fields.** The signed body includes the full
   provenance dump — `timestamp`, `alleleforge_version`, `config_snapshot` — and hashes
   unrounded floats (`runner.py:390-403`, `_canon.py:20`); the real CLI path stamps
   wall-clock time (`cli/main.py:949` passes no `timestamp`). So the signature is a
   same-artifact tamper seal, not the reproducibility digest the module advertises
   (`runner.py:11-13`): a second lab, a new release, or a different platform (KL-metric
   tasks) produces a different signature for a scientifically identical result — and can't
   distinguish that from tampering. `reproduce.py:55-69` already strips these keys and rounds
   floats for exactly this reason.
2. **The benchmark `config_snapshot` is a hand-built 2-key subset.**
   `config_snapshot={"task": …, "split_version": …}` (`runner.py:380`) is precisely the
   hand-built subset the provenance spec forbids ("full resolved settings … not a hand-built
   subset"). `Settings.snapshot()` exists (`config.py:92`) and the design path already uses
   it. The omitted settings include `interval_level` (default 0.80), which drives the
   baseline's predictive interval and therefore the regression **ECE** the leaderboard ranks
   honesty by — so two results with different interval levels look comparable but are not.
3. **The result never binds the split membership hash.** The signed body records
   `split_version` (the label `"v1"`) and the dataset content hash, but not
   `split.split_sha256` (`splits/__init__.py:62-74` computes it; it is used only at load).
   A result binds *which dataset* but not *which partition* — if a `v1` split were re-cut
   over the same rows, the result still reads `v1` and a consumer can't tell whether the
   model or the fold moved.
4. **Degenerate predictions score ECE = 0.0 ("perfectly calibrated").** ECE returns `0.0`
   for empty inputs (`metrics.py:205`), and a distribution scorer that emits `{}` everywhere
   contributes no confidence pairs (`runner.py:190-195`) → ECE `0.0` — the *best* value,
   which then wins the leaderboard's calibration tie-break (`leaderboard.py:167-173`). A
   model that expressed no calibrated belief is reported as perfectly calibrated and can
   out-rank an honest competitor.

## What Changes

- **Add a reproducibility digest** over only the scientific body — metrics (rounded to a
  fixed precision), model-card facts, task, split identity, and dataset hash — excluding
  wall-clock timestamp, package version, and local config paths, so two independent runs of
  the same model on the same frozen `(task, split)` produce the identical digest across
  releases and platforms. (Reuse the `reproduce.py` canonicalization.)
- **Populate the benchmark `config_snapshot` from `Settings.snapshot()`** so it records
  `interval_level` and every setting that governed the metrics, like the design path.
- **Bind the split's `split_sha256`** into the signed body, so a verifier can confirm the
  exact frozen fold membership, not just a version label.
- **Distinguish "undefined" calibration from "perfect":** an ECE with too few scorable
  predictions to estimate reliability SHALL be surfaced as undefined (null/`n/a`) and
  excluded from — or penalized in — ranking, so no model earns a perfect honesty score by
  emitting no real prediction.

## Impact

- Specs: `benchmark-harness` (ADDED reproducibility digest; ADDED split-hash binding;
  MODIFIED undefined-vs-perfect calibration), `provenance-reproducibility` (ADDED
  full-snapshot for benchmark results).
- Code: `benchmark/runner.py`, `benchmark/metrics.py`, `benchmark/leaderboard.py`,
  `benchmark/_canon.py`, `cli/main.py`; a shared "canonical scientific body" helper reused
  by `scripts/reproduce.py`.
- Tests: the same model on the same `(task, split)` yields the same digest across a version
  bump and a fixed/absent timestamp; a benchmark result's `config_snapshot` carries
  `interval_level`; a re-cut split changes the bound hash; a `{}`-everywhere scorer reports
  undefined ECE and does not win the tie-break.
