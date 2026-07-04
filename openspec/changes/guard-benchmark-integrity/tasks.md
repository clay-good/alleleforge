# Tasks

## 1. Enforce split integrity
- [ ] 1.1 In `Split.verify`/`load_split`, raise if `train`/`val`/`test` overlap.
- [ ] 1.2 Raise if any split id is absent from the dataset.
- [ ] 1.3 Tests for both.

## 2. Schema versioning
- [ ] 2.1 Add a `schema_version` to `BenchmarkResult` and to the TSV/Parquet exports.
- [ ] 2.2 Test: exports carry the version; a bump is detectable.

## 3. Leaderboard safety
- [ ] 3.1 HTML-escape and Markdown-escape `model_name`/`submitter`/`task` in the renders.
- [ ] 3.2 Enforce per-(model, task) uniqueness in a submission.
- [ ] 3.3 Tests: a markup handle is escaped; a duplicate (model, task) is rejected.

## 4. Optional metric hardening
- [ ] 4.1 (Optional) Make `pr_auc` tie-grouping order-insensitive; note `roc_auc` O(n^2)
      scaling for large folds.

## 5. Reconcile
- [ ] 5.1 `make ci` green.
