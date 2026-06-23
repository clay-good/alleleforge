# Base-editing outcome model — next real-model target

_Status as of 2026-06-23. Third real-model integration (after Rule Set 3 and
PRIDICT2.0). Captures the research + plan; implementation is the next unit._

## Decision: BE-DICT first

The base-editing **outcome** scorers (`scoring/base_outcome.py`: `BeDictAdapter`,
`BeHiveAdapter`) are still heuristic placeholders / `NotImplementedError` stubs.
Two real candidates:

- **BE-DICT** (`uzh-dqbm-cmi/crispr`) — **chosen first.** MIT; PyTorch; **same lab
  as PRIDICT2** (whose modern stack already runs here, so low rot risk); two models:
  `perbase` (per-position edit probability) and `bystander` (haplotype/allele
  distribution). Weights in-repo. Refs: https://github.com/uzh-dqbm-cmi/crispr ,
  https://www.nature.com/articles/s41467-021-25375-z
- **BE-Hive** (Arbab 2020, Broad) — deferred. Older (2020), higher rot risk;
  deep conditional autoregressive. Refs: https://www.broadinstitute.org/news/new-machine-learning-tool-predicts-base-editing-outcomes

## Why this is more involved than the efficiency models

RS3/PRIDICT2 return a scalar efficiency → a single `Prediction[float]`. BE-DICT's
**bystander** model returns a **distribution over edited alleles** in the activity
window, which must map onto AlleleForge's existing base-edit outcome types
(`WindowOutcome` / the allele distribution consumed by `base_outcome.py` and the
ranking's "cleanliness"/bystander-burden axis). The integration is therefore an
*outcome* adapter, not a scalar scorer — get the allele-distribution mapping right.

## Plan (mirrors the proven pattern)

1. Feasibility + golden capture: clone, install in an isolated env, run the
   `bystander` demo, capture a reference allele distribution for a known sgRNA.
2. Adapter: a `BeDictAdapter`-style outcome predictor resolving weights through the
   model-zoo gate (BE-DICT is MIT). Decide the boundary like PRIDICT2:
   - If BE-DICT exposes a clean in-process inference on modern torch → in-process
     adapter (preferred; BE-DICT is plain PyTorch, likely importable unlike
     PRIDICT2's dual-framework CLI).
   - Else → subprocess wrapper to its own env (the PRIDICT2 pattern).
3. Map BE-DICT's allele distribution → AlleleForge's base-edit outcome type; keep
   honest flags (`calibrated=False` until conformal calibration).
4. Tests: CI parses a fixture distribution + exercises the gate; `real_weights`
   golden test reproduces the captured distribution. Card: update
   `cards/be-dict.yaml` (license, pin if a stable artifact is chosen).
5. Docs/README: honest real-vs-heuristic for the base-editing outcome axis.

## Constraints carried forward

Lazy imports; opt-in extra; `real_weights`-gated; weight-free CI untouched; honest
`method`/`calibrated`; no new hard dep on the heavy stack.

## Feasibility: CONFIRMED — BE-DICT runs on modern torch/py3.11

Installed BE-DICT (`pip install -e .`, unpinned deps) and ran the **perbase** model
on the sample data. It loads the 5-fold ensemble and predicts cleanly. Two gotchas:

- `select_prediction(..., 'mean')` breaks on modern pandas (it `.mean()`s a frame
  with the string `run_id` column). Aggregate the ensemble manually instead:
  `pred_runs.groupby('base_pos')['prob_score_class1'].mean()`.
- `_load_model_statedict_` loads weights from `<cwd_parent>/trained_models/perbase/
  {editor}/train_val/run_{n}` — i.e. **cwd-relative** (assumes cwd is a subdir of the
  repo). The adapter must set cwd into the BE-DICT checkout (or patch the path).

### API

- `from criscas.predict_model import BEDICT_CriscasModel`
- `BEDICT_CriscasModel(base_editor, torch.device('cpu')).predict_from_dataframe(df)`
  → `(pred_runs_df, proc_df)`. Input `df` columns: `ID`, `seq` (20-nt protospacer).
- Editors: `ABEmax`, `ABE8e`, `BE4max`, `Target-AID` (perbase + bystander variants).
- Output `pred_runs_df`: one row per (`id`, `base_pos`) per run; `prob_score_class1`
  = P(position edited). `base_pos` = **0-indexed** position of the target base.

### Golden (perbase, ABEmax, seq `ACACACACACTTAGAATCTG`, mean over 5 runs)

| base_pos (0-idx) | P(edit) |
|---|---|
| 0 | 0.00067 |
| 2 | 0.02460 |
| 4 | 0.94198 |
| 6 | 0.72816 |
| 8 | 0.07536 |
| 12 | 0.00595 |
| 14 | 0.00120 |
| 15 | 0.00013 |

(Window peaks at pos 4–6 — biologically correct for ABE.)

## ⚠ Correctness-critical: position-convention reconciliation (verify before wiring)

`BaseEditWindow.target_positions`/`bystander_positions` are **1-based, counting from
the PAM-distal end** (`types/guide.py`). BE-DICT `base_pos` is **0-based**. The
mapping is *probably* AlleleForge `p` ↔ BE-DICT `p-1` (both from the PAM-distal/5'
end), but this **must be verified** against BE-DICT's training orientation (which end
is index 0, and whether the 20-mer is PAM-distal-first) — an off-by-one or flipped
orientation silently yields wrong outcomes. Do not ship the adapter until a test
pins this against BE-DICT's own documented window (ABE/CBE canonical window ≈ 1-based
4–8 from PAM-distal). This is the one open item; everything else is ready.

## Implementation shape (ready once the mapping is verified)

- `BeDictAdapter.predict(window, editor)`: map AlleleForge editor → BE-DICT editor
  name; run perbase; mean over runs → per-position P(edit); reuse the **existing**
  baseline allele enumeration (`itertools.combinations`) with the real probabilities
  to build `EditOutcome` + `p_intended_exact` + `bystander_burden`.
- Boundary: BE-DICT is pure PyTorch (no TF/typing-extensions conflict, unlike
  PRIDICT2), so in-process is viable with a cwd-context-manager into the checkout;
  point at it via `$ALLELEFORGE_BEDICT_REPO`. Gated behind `real_weights`; CI parses
  a fixture of the golden table + exercises the gate.

## Execution log

- 2026-06-23: Researched BE-DICT (MIT, PyTorch, same lab as PRIDICT2) and BE-Hive
  (older, deferred). Chose BE-DICT.
- 2026-06-23: **De-risked fully.** Installed + ran the perbase model on modern
  torch/py3.11; captured the golden table above; mapped the output to the existing
  allele-enumeration path. Flagged the one correctness-critical open item: the
  1-based-PAM-distal ↔ 0-based position reconciliation.
- 2026-06-23: **SHIPPED + verified.** Position mapping confirmed by AlleleForge's own
  `_editable_positions` (1-based, `spacer[p-1]`) ⇒ BE-DICT `base_pos p-1`; both 5'→3'.
  `BeDictAdapter` (real) wired in `scoring/base_outcome.py`: runs BE-DICT in-process
  (cwd-guard + `sys.path`), aggregates the 5-fold ensemble (manual mean — upstream
  `select_prediction` breaks on modern pandas), maps positions, and reuses the shared
  `_assemble_window_outcome`. Editors: ABE8e→ABE8e, CBE4max→BE4max (evoCDA1
  unsupported → `ValueError`). Gated behind `real_weights`. Live golden test **PASSED**
  (ABE8e, seq `ACACACACACTTAGAATCTG`: base_pos 4≈0.776, 6≈0.577; full `predict`
  pins target pos 5 → base_pos 4 peak). Card `source_url` corrected (`crispr-bedict`
  → `crispr`). `make ci` green.
- **BE-Hive** remains the deferred follow-up; **PRIDICT2 P2** (per-pegRNA parity) and
  **Cas9 outcome** (inDelphi/Lindel/X-CRISP) are the other open outcome-model items.
