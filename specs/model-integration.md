# Model integration spec — wire + validate the first real model

_Status as of 2026-06-23. Execution target #1 from
[`readiness-assessment.md`](readiness-assessment.md)._

## Decision: Rule Set 3 first

Chosen over PRIDICT2.0 because:

- `rs3` (Rule Set 3, gpp-rnd/Broad) is **on PyPI**, **CPU-only**, no torch/GPU.
- **PRIDICT2.0 has no PyPI package** (GitHub-only, heavier TF/RNN stack) → harder; it
  is target #2.
- Closes the documented hook in `src/alleleforge/scoring/cas9_efficiency.py`:
  "The exact trained RS3 coefficients load through the model zoo when present."

PRIDICT2.0 remains the higher *unique* value (prime editing is the four-axis gap), so
it is the next model after this one proves the path.

## Upstream facts (`rs3` v0.0.18)

- Trained **LightGBM** "sequence" model; `from rs3.seq import predict_seq`.
- Deps pin **old**: `scikit-learn<=1.0.2`, `numpy<=1.26.4`, `lightgbm<=3.3.5`,
  `pandas`, `biopython`, `requests`. **Conflicts with the `ml` extra** (`scikit-learn>=1.4`).
- Downloads its trained model file on first use (fits the model-zoo "authorize then
  load by the model's own source" path; card `checkpoint_sha256: null`).
- Input is a **30-mer** context: 4 nt 5' + 20 nt protospacer + 3 nt PAM + 3 nt 3'.
  (The shipped benchmark fixture contexts are **23-mers** and **synthetic** — see
  Validation.)
- Refs: https://github.com/gpp-rnd/rs3 , https://pypi.org/project/rs3/

## Design constraints (must hold)

1. **CI stays weight-free.** The real path is gated behind the `real_weights` pytest
   marker and a lazy `import rs3` inside the gated method. The library never hard-
   depends on `rs3`. Main `.venv` and `make ci` must keep passing untouched.
2. **Goes through the existing gate.** Use `WeightGate` / the model-zoo
   consent+license `authorize` path; record the resolved `ModelCheckpoint` for
   provenance. Default scorer behavior is unchanged unless real weights are opted in.
3. **Isolated optional extra.** Add `cas9-rs3 = ["rs3>=0.0.18"]` to
   `pyproject.toml`, documented: install in an isolated environment due to upstream's
   pinned deps. Not part of `ml`/`dev`.
4. **Honest Prediction.** When the real model runs: `calibrated=True` only if we
   actually calibrate; otherwise keep `calibrated=False` but set
   `method` to a non-HEURISTIC value reflecting the trained model. OOD flag honored
   (RS3 trained on lentiviral pooled screens).

## Implementation plan

- Add `TrainedRuleSet3Scorer` (or extend `RuleSet3Scorer` with a
  `use_trained_weights` path) in `scoring/cas9_efficiency.py`:
  - Mixes in `WeightGate`, `card_name = "rule-set-3"`.
  - `score(context_30mer)`: `resolve_weights()` (consent/license), lazy `import rs3`,
    call `predict_seq([...])`, wrap the float in a calibrated `Prediction` with the
    recorded checkpoint provenance.
  - Raise a clear error if context length != 30 (RS3 contract).
- `pyproject.toml`: add the `cas9-rs3` optional extra.
- Docs: note the new opt-in path + the isolated-env caveat.

## Validation (honest)

The shipped fixtures are synthetic + 23-mer, so **published-Spearman reproduction is
not possible from in-repo data**. Correct validation here:

1. **Parity with upstream** (the gold standard for "wired correctly"): a
   `real_weights`-marked test asserting our adapter's score == `rs3.seq.predict_seq`
   on the same 30-mer inputs (skipped if `rs3` not importable / no network). This is
   the same parity discipline the repo uses for its Rust kernels.
2. **Runs on real inputs**: a small end-to-end demonstration on real 30-mer contexts.
3. **Documented gap**: reproducing the published Spearman requires the real, non-
   redistributable RS3 validation library, fetched at runtime — out of scope for the
   committed test suite; record the procedure, not the data.

## Done criteria

- [x] `cas9-rs3` extra added (`lightgbm`, `sglearn`); lazy import; no new hard dep.
- [x] `TrainedRuleSet3Scorer` wired through `WeightGate`; returns a provenance-
      stamped `Prediction` (trained point estimate, heuristic interval).
- [x] `real_weights` parity test (adapter == upstream, golden z-scores) added;
      skips cleanly without the extra / booster.
- [x] `make ci` still fully green (weight-free path unchanged) — see log.
- [x] Docs + README honestly describe real vs heuristic; license corrected.
- [x] Live real-data run captured (parity PASSED in a `cas9-rs3` env).

## Chosen design (Option B, as built)

- **Vendored artifact:** the version-independent LightGBM **text booster**
  `RuleSet3.txt` (sha256 `464a5a08…917e`), derived from `rs3` v0.0.18 by
  `scripts/export_rs3_booster.py`. Hosted by the maintainer at the card's
  `source_url`; the gate downloads + checksum-verifies it (closes R0 for this
  model). NOT committed to the repo (keeps the core light).
- **Featurization:** reuse the modern-Python-compatible upstream `sglearn`
  featurizer (632 features incl. 5 thermodynamic ones via `seqfold`) — reused
  rather than reimplemented, because the thermodynamic features make a from-
  scratch rewrite parity-risky. This is the only deviation from the literal
  "reimplement in-tree" wording; it *guarantees* parity instead of risking it.
- **Runtime:** modern `lightgbm>=4` loads the text booster (sidesteps the rotted
  `lightgbm<=3.3.5` pickle); `sglearn` does featurization. No torch, no legacy pins.
- **Prediction:** value = logistic(RS3 z-score) ∈ [0,1] (monotone, ranking-
  preserving); raw z-score via `predict_raw`; interval heuristic; `calibrated=False`.

## Execution log (continued)

- 2026-06-23: Implemented + verified. Exact parity (text booster vs upstream pkl =
  0.0 diff). Live `real_weights` parity test PASSED in a fresh `alleleforge[cas9-rs3]`
  env (golden Chen2013 z-scores `[-0.349795, -2.422439, -1.315348]` reproduced).
  Weight-free CI path unchanged. License corrected BSD-3 → Apache-2.0 (the actual
  `rs3` license) + registry test updated.
- **Follow-up for the maintainer:** run `scripts/export_rs3_booster.py` in a legacy
  env, upload `RuleSet3.txt` as the `rs3-booster-v1` release asset (the card's
  `source_url`), and confirm its sha256 matches the card. Until hosted, the trained
  path works only with an injected/local booster (as the parity test does).
- **Next model:** PRIDICT2.0 (prime efficiency) — no PyPI pkg, heavier; apply the
  same text-export/version-stable pattern if its weights permit.

## Execution log

- 2026-06-23: spec written; decision = Rule Set 3 via `rs3`. Starting implementation.
- 2026-06-23: **Validated real RS3 in an isolated venv — it runs.** Parity ground
  truth obtained: `predict_seq` returns **raw activity z-scores** (not 0–1), e.g.
  Chen2013 `[-0.3498, -2.42244, -1.31535]` for three test 30-mers; Hsu2013 differs
  (tracr-aware); 632 features; deterministic. Higher = more active.
- 2026-06-23: **Packaging finding (decision-changing).** `rs3` is hostile to modern
  Python:
  - pins `scikit-learn<=1.0.2` → no cp311/cp312 wheel, source build fails (Cython).
  - pins `lightgbm<=3.3.5` → no cp311/cp312 wheel, source build fails.
  - its `RuleSet3.pkl` won't load under modern LightGBM without patching
    `model._n_classes = 1` (old sklearn-wrapper pickle).
  - also needs `libomp` (brew), `seqfold`, `sglearn`, `packaging`.
  - Net: a clean `pip install alleleforge[cas9-rs3]` on Python 3.11+ **fails**. It
    only runs in a pinned legacy env (Python ≤3.10 + old sklearn/lightgbm) or with
    the model-load patch + relaxed deps.
  - PRIDICT2.0 has **no PyPI package** at all → even harder.

## Fork (awaiting user decision)

- **(A) Wrap `rs3` as-is, opt-in + gated.** Lazy `import rs3`, gated behind
  `real_weights`, parity-tested, skipped in CI. Honestly documented as requiring a
  legacy env. Consistent with the repo's "real weights are opt-in, never in CI"
  philosophy. Fast; real RS3 proven. UX: brittle install is the user's burden.
- **(B) Vendor RS3 cleanly, version-stable.** Export the LightGBM model to the
  version-independent native **text booster** (`booster_.save_model()`) so it loads
  on any LightGBM, and reimplement the `sglearn` 632-feature featurization in-tree.
  Clean modern UX, reproducible, no legacy pins — but significant work + feature-
  parity risk + redistribution review.
- **(C) Different first model.** Ship a cleanly-packageable real published model
  first (e.g. a vendored linear model — Doench 2014 Rule Set 1 / Moreno-Mateos
  CRISPRScan — implementable from published coefficients with zero heavy deps), and
  keep RS3/PRIDICT2 as documented legacy opt-in adapters.
