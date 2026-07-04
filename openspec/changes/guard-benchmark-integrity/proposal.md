# Guard benchmark integrity: split leakage and schema drift

## Why

CRISPR-Bench's trustworthiness rests on invariants that are not all checked:

- **Split leakage is not structurally prevented.** `Split.verify` hashes whatever
  membership is in the file but never checks that `train`/`val`/`test` are disjoint
  (`benchmark/splits/__init__.py:76-94`). A minted split with an id in both train and test
  passes every integrity check — the one thing a benchmark most needs to forbid.
- **Dangling ids pass verification.** `verify` does not confirm every split id exists in
  the dataset; a missing id only surfaces later as a `KeyError` in `examples()`.
- **No schema/format version on results or exports.** `BenchmarkResult`, `TSV_COLUMNS`, and
  the Parquet frame carry no version tag, so adding or reordering a field is undetectable
  silent drift for downstream consumers.
- **Leaderboard cells are unescaped.** `model_name`, `submitter`, and `task` interpolate
  raw into HTML/Markdown (`benchmark/leaderboard.py:185-195, 165-168`) — a submitter handle
  with markup is an injection vector in the static board, and a `|` breaks the table.
- A submitter may also submit **two results for the same task**, both of which rank
  (`leaderboard.py:113-125`).

## What Changes

- **Enforce split disjointness and id existence** at load: raise if `train`/`val`/`test`
  overlap or if any split id is missing from the dataset.
- Add a **schema/format version** to `BenchmarkResult` and to the TSV/Parquet exports, so
  consumers can detect drift.
- **Escape leaderboard cell content** in the HTML and Markdown renders.
- Enforce **per-(model, task) uniqueness** in a submission.

## Impact

- Specs: `benchmark-harness` (ADDED split-disjointness + id-existence; ADDED result schema
  version; ADDED per-model-task uniqueness), `reporting` (ADDED leaderboard escaping and
  export schema version).
- Code: `benchmark/splits/__init__.py`, `benchmark/runner.py`, `benchmark/leaderboard.py`,
  `benchmark/metrics.py` (optional: grouped-tie handling in `pr_auc`), `report/export.py`.
- Tests: an overlapping split is rejected; a dangling id is rejected; a duplicate
  (model, task) submission is rejected; a leaderboard entry with markup is escaped; exports
  carry a schema version.
