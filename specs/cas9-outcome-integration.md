# Cas9 outcome model integration — Lindel (shipped) + the remaining stubs

_Status as of 2026-06-23. Fourth real-model integration. With this, every major
prediction axis has at least one real model: Cas9 efficiency (Rule Set 3), prime
efficiency (PRIDICT2.0), base-edit outcome (BE-DICT), **Cas9 outcome (Lindel)**._

## Shipped: LindelAdapter

`scoring/cas9_outcome.py` — the real **Lindel** logistic-regression indel model
(Chen et al., *Nucleic Acids Res* 2019), the first real model on the Cas9 outcome
axis (the `MicrohomologyOutcomePredictor` baseline stays the weight-free default).

- **Why Lindel first** of {inDelphi, Lindel, X-CRISP}: pure NumPy/SciPy (no torch),
  small pickled weights bundled in the repo, clean `gen_prediction` API.
- **Input:** Lindel's fixed 60-bp window (30 bp each side of the cut); built from
  AlleleForge `(context, cut)` by `_lindel_window`. Requires an NGG PAM at the
  expected offset (Lindel returns an error string otherwise → `ValueError`).
- **Output mapping (`_lindel_outcome`, pure + CI-tested):** Lindel's 557-class
  distribution → a normalized `EditOutcome`. Top-`k` classes kept verbatim; the tail
  is bucketed into `other_frameshift` / `other_inframe` so the **total frameshift
  mass is preserved exactly** (it equals Lindel's frameshift ratio, which the
  knock-out ranking reads via `p_intended`).
- **Boundary:** Lindel ships as a Git repo (not PyPI). The adapter points at a
  checkout via `repo_dir` / `$ALLELEFORGE_LINDEL_REPO` and imports it on `sys.path`
  (weights load from `Lindel.__path__`, not cwd-relative — simpler than BE-DICT). No
  new hard dep; gated behind `real_weights`; CI parses pure helpers + the gate.
- **Verified:** live `real_weights` golden test passed — example 60-mer reproduced
  Lindel's frameshift ratio **0.8912** and top class **`-2+4`** (p≈0.309); the
  `EditOutcome` is normalized. `make ci` green.

`LindelAdapter.predict(context, cut, *, max_del, mark_frameshift)` matches the
`Cas9OutcomePredictor` protocol, so it is a drop-in for `design_cas9`'s
`outcome_predictor` (a `--trained-outcome` CLI flag could expose it, mirroring
`--trained-efficiency`).

## Remaining outcome/cross-check stubs (still `NotImplementedError`)

In broad scope but lower priority — each axis they touch already has a real model:

- **inDelphi** (Cas9 outcome) — TensorFlow/Theano-era (2018); higher rot risk. The
  MMEJ baseline already mirrors its mechanism. Cross-check alternative to Lindel.
- **X-CRISP** (Cas9 outcome) — newer; assess like Lindel.
- **DeepPrime / GenET** (prime efficiency cross-check) — alternatives to the wired
  PRIDICT2.0 engine.
- **BE-Hive** (base-edit outcome cross-check) — older (2020); alternative to BE-DICT.

These are redundant cross-checks; the ensemble/agreement machinery
(`ensemble_outcome`) is where they'd add value (inter-model uncertainty), not new
coverage. Wire on demand following the same proven pattern.

## Execution log

- 2026-06-23: Installed + ran Lindel (NumPy, 557 classes, frameshift ratio 0.8912);
  mapped its distribution to `EditOutcome` (frameshift-preserving buckets); shipped
  `LindelAdapter` with pure CI-tested helpers + a live-passing `real_weights` golden.
