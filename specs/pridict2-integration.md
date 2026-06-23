# PRIDICT2.0 integration spec — target model #2 (prime efficiency)

_Status as of 2026-06-23. Follows the RS3 integration
([`model-integration.md`](model-integration.md)). PRIDICT2 is a substantially
bigger lift than RS3; this spec records the research, the boundary decision, and a
staged plan so it can be executed without rediscovery._

## Research findings (uzh-dqbm-cmi/PRIDICT2)

- **License: MIT** — fully redistributable (weights included). Best case.
- **Architecture:** an ensemble of attention-based bidirectional RNNs (PyTorch),
  per cell line (**HEK**, **K562**), across **5 folds** (`--use_5folds` averages
  them; default uses fold-1). Many sub-modules per run (init/mut encoders,
  global/local feature-embedding attention, decoders) saved as `.pkl` state dicts
  under `trained_models/pridict1_2/.../model_statedict/`.
- **Second framework:** a **TensorFlow 2.13** DeepCas9/DeepSpCas9 model
  (`trained_models/DeepCas9_Final`, TF checkpoint) computes a **required** input
  feature (the nicking-guide Cas9 score). The prediction path imports it
  (`pridict2_pegRNA_design.py:deepcas9()`), so TF is **not** optional.
- **Stack:** Python 3.10/3.11, `torch==2.0.1` (CPU), `tensorflow==2.13.1`,
  `pandas==2.0.3`, `scikit-learn==1.3.0`, `scipy==1.11.1`, `biopython==1.81`,
  `primer3-py`, `prettytable`, `tqdm`. **Modern enough**: both TF 2.13.1 and torch
  2.0.1 ship **cp311 macOS-arm64 wheels**, so the stack installs/runs on Python
  3.11 (unlike rs3's rotted pins).
- **Interface (the key mismatch):** sequence-in → ranked-pegRNA-designs-out.
  `python pridict2_pegRNA_design.py single --sequence-name X --sequence "...(a/g)..."`
  (≥100 bp up/downstream of the bracketed edit). It **designs its own pegRNAs** and
  scores them; it does **not** expose "score this externally-supplied pegRNA".
  Output: a CSV of designs with `PRIDICT2_0_editing_Score_deep_HEK`/`..._K562` etc.

## The integration-boundary decision (needs user input)

AlleleForge's `PridictScorer.score(pegrna)` scores a **specific** pegRNA that
AlleleForge enumerated. PRIDICT2 designs+scores **its own** pegRNAs. So:

- **(P1) Sequence-level adapter (wrap, achievable).** Give PRIDICT2 the edit's
  genomic context (AlleleForge already has it from the resolved variant + reference)
  and surface PRIDICT2's ranked designs + efficiencies. True "wrap, don't rebuild".
  New-ish API surface (a designer/provider, not a drop-in `Scorer`). Achievable now
  (the stack runs here).
- **(P2) Per-pegRNA parity scorer (faithful drop-in, large).** Reproduce PRIDICT2's
  exact featurization for an arbitrary pegRNA + run the ensemble forward pass, so it
  scores AlleleForge's own enumerated pegRNAs. Matches the existing `Scorer`
  contract and `DeepPrimeAdapter` slot, but requires reverse-engineering the large
  `data_preprocess.py` featurization + loading the multi-module ensemble + ONNX/
  version-stable export. Multi-session.

Recommendation: **start with P1** (real value now, faithful, low risk), and treat
P2 as a later enhancement once P1 proves the wiring. P1 also yields the golden
reference data P2 would validate against.

## Staged plan

1. **[in progress] Feasibility + reference capture.** Install the stack in an
   isolated py3.11 env, run `single` on a known sequence, capture the output CSV as
   golden reference data. (Confirms the MIT model runs here.)
2. **Adapter (P1).** Add an opt-in `prime-pridict` extra and a wrapper that invokes
   PRIDICT2's pipeline for a target sequence, parses the efficiency, and returns it
   through the model-zoo gate (consent/license; MIT permits commercial too). Gated
   behind `real_weights`; CI stays weight-free. Golden test vs the captured CSV.
3. **Provenance + card.** Update `cards/pridict2.yaml` (license already MIT; pin the
   weights once a stable artifact/host is chosen — the repo is the source).
4. **(Later, P2)** per-pegRNA parity scorer + version-stable export.

## Constraints carried from RS3

- Lazy imports; no new hard dep; opt-in extra; `real_weights`-gated; honest
  `method`/`calibrated` flags; weight-free CI untouched.

## Boundary decision: P1 (sequence-level wrap) — chosen by maintainer (2026-06-23)

Build the sequence-level adapter that wraps PRIDICT2's own pipeline. P2 (per-pegRNA
parity) is a later enhancement validated against P1's captured references.

## Feasibility: CONFIRMED (real model ran here)

Installed the stack in an isolated py3.11 env (`torch==2.0.1` CPU, `tensorflow==2.13.1`,
`pandas==2.0.3`, `numpy==1.24.3` — TF's pin; `matplotlib/seaborn/scikit-learn/scipy/
biopython/primer3-py/prettytable/tqdm`) and ran:

    python pridict2_pegRNA_design.py single --sequence-name af_demo --sequence "<…(A/G)…>"

It produced `af_demo_pegRNA_Pridict_full.csv`: **612 pegRNA designs × 51 columns**.
Efficiency lives in `PRIDICT2_0_editing_Score_deep_HEK` / `…_K562` (0–100 scale).

**Golden reference (top design by HEK score), for the parity test:**

| Editing_Position | PBSlength | RTlength | RToverhang | K562 | HEK |
|---|---|---|---|---|---|
| 8 | 15 | 16 | 7 | 23.2140 | 76.7831 |
| 8 | 14 | 16 | 7 | 22.7780 | 77.1121 |
| 3 | 15 | 11 | 7 | 22.0960 | 68.8809 |

(Default = fold-1; `--use_5folds` averages the ensemble. numpy ABI note: install
`matplotlib` BEFORE pinning `numpy==1.24.3`, or it drags in numpy 2.x and breaks the
TF/pandas ABI.)

## P1 implementation sketch (next unit)

- `PridictEngineAdapter` (sequence-level, not a `Scorer`): wraps the PRIDICT2
  `single` CLI via subprocess. Locate the checkout + interpreter via constructor
  args defaulting to `$ALLELEFORGE_PRIDICT2_REPO` / `$ALLELEFORGE_PRIDICT2_PYTHON`
  (PRIDICT2 isn't pip-installable, so it can't be a normal extra — it's an external
  tool the user clones; the adapter shells out to it).
- Returns parsed top-N designs as a small `PridictDesign` result carrying a
  `Prediction[float]` efficiency (value = HEK/K562 score ÷ 100; interval from the
  5-fold spread when `use_5folds`, else heuristic; `method` reflects the trained
  model; OOD honest about HEK/K562 training).
- Model-zoo gate: `authorize` the `pridict2` card for provenance (license MIT →
  permits research *and* commercial, unlike NT v2).
- Tests: CI parses a tiny committed fixture CSV + exercises the gate; a
  `real_weights` golden test runs the real CLI when `$ALLELEFORGE_PRIDICT2_REPO` +
  env are present and asserts the top-design HEK/K562 scores above.
- **No `prime-pridict` extra is needed.** Because the adapter *shells out* to
  PRIDICT2's own interpreter (`$ALLELEFORGE_PRIDICT2_PYTHON`), AlleleForge's process
  uses only stdlib (`csv`, `subprocess`) — it never imports torch/TF. This also
  sidesteps a hard conflict: pydantic (AlleleForge) needs `typing-extensions>=4.6`
  while TF 2.13 needs `<4.6`, so the two stacks *cannot* share one env. Keeping
  PRIDICT2 in its own env is therefore both cleaner and necessary. Docs: the user
  clones the MIT repo + builds its env, then points the adapter at it.

## Execution log

- 2026-06-23: Researched repo (MIT; TF DeepCas9 + torch RNN ensemble; sequence→
  designs; cp311 arm64 wheels exist). Installed stack, **ran the real model**, captured
  the golden reference above. Boundary chosen = P1.
- 2026-06-23: **P1 SHIPPED.** `PridictEngineAdapter` + `PridictDesign` in
  `scoring/pridict_engine.py` (stdlib-only; subprocess wrapper; model-zoo gated;
  `real_weights`-marked). CI tests parse a real-data fixture
  (`tests/scoring/fixtures/pridict2_sample.csv`) + exercise the consent gate. The
  `real_weights` golden test **PASSED live**: run from the main `.venv` with the
  subprocess pointed at the PRIDICT2 env, it reproduced the top-design HEK
  efficiency (0.78854) within 5e-3. `make ci` stays green/weight-free.
- **Next (P2):** per-pegRNA parity scorer + version-stable (ONNX) export, validated
  against P1's captured references.

## Prime per-pegRNA cross-check: DeepPrime via GenET (fills DeepPrimeAdapter/GenETAdapter)

Research 2026-06-23. The `DeepPrimeAdapter` / `GenETAdapter` stubs (prime efficiency
cross-checks) have a **clean path**: the **`genet`** package is on **PyPI**
(`pip install genet`) and wraps DeepPrime (Yu et al., *Cell* 2023). It exposes a
**per-pegRNA** API — exactly the `score(pegrna) -> Prediction` slot, and the
per-pegRNA prime scorer PRIDICT2's sequence-level engine lacks (so this also
satisfies the P2 need from a different model):

    from genet.predict import DeepPrimeGuideRNA
    peg = DeepPrimeGuideRNA('id', target=..., pbs=..., rtt=..., edit_len=1,
                            edit_pos=16, edit_type='sub')
    score = peg.predict('PE2max')   # single efficiency

Integration shape: map AlleleForge `PegRNA` (spacer/pbs/rtt + edit) →
`DeepPrimeGuideRNA(target, pbs, rtt, edit_len, edit_pos, edit_type)`; wrap the score
as a `Prediction`. **Correctness-critical** (do not rush): `target` orientation and
`edit_pos` indexing must be pinned by a golden test against GenET's own output, like
the BE-DICT position mapping. Heavy deps (torch + TF≥2.6), so opt-in extra
(`prime-genet`) or a checkout-style env, gated behind `real_weights`. The other prime
cross-check (X-CRISP is Cas9-outcome, not prime) does not apply here.
