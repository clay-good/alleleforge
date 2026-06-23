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

## Execution log

- 2026-06-23: Researched BE-DICT (MIT, PyTorch, same lab as PRIDICT2) and BE-Hive
  (older, deferred). Chose BE-DICT. Implementation queued as the next unit.
