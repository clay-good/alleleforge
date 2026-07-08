# Tasks

## 1. OOD widening floor — DONE

- [x] In `scoring/uncertainty.py`, add an additive minimum half-width floor to the OOD
  widening path so the interval is strictly wider than any in-distribution interval the
  same head could produce, and a zero-width interval cannot survive OOD flagging.
  (`OOD_MIN_HALF_WIDTH = 0.05`, added on top of `OOD_WIDEN_FACTOR` in `to_prediction`.)
- [x] Test: an OOD prediction whose ensemble members agree exactly (`std == 0`) returns a
  non-zero-width interval and `calibrated = False`.
  (`test_ood_floor_defeats_zero_width_agreement`.)

## 2. Compute in_distribution; fail honest by default — DONE

- [x] Change every scorer that emits a `Prediction` (`cas9_efficiency.py`,
  `prime_efficiency.py`, `prime_outcome.py`, `base_outcome.py`, `pridict_engine.py`) to
  derive `in_distribution` from an explicit distribution check; a scorer with no detector
  SHALL default `in_distribution = False`, never `True`.
  (No emitting scorer now hardcodes `True`: cas9 ensemble falls back to
  `context_in_distribution`; prime-outcome and base-outcome compute an N-free reagent check;
  pridict computes from the cell line. `prime_efficiency` already had a cell-context check;
  the trained `_ModelZooAdapter` placeholders never emit a Prediction (they raise); Lindel /
  cas9-outcome adapters return an `EditOutcome` distribution, not a scalar `Prediction`.)
- [x] Wire a training reference + `OODDetector` (or a documented context check) into the
  default ensemble, prime, and base scorers used by `design/`.
  (Shared `cas9_efficiency.context_in_distribution` (N-free + min length) is the default
  ensemble's fallback when no embedding-space `OODDetector` is wired; prime-outcome and
  base-outcome apply the analogous reagent-sequence check. Well-formed reference contexts
  stay in-distribution — no golden churn — while N-bearing / too-short inputs now flag OOD.)
- [x] Give the trained PRIDICT/BE-DICT/Lindel adapters at least the OOD check their
  heuristic baselines already apply (e.g. cell-context membership).
  (`PridictEngineAdapter._efficiency` now takes `cell_line` and computes
  `in_distribution = cell_line in PRIDICT2_CELL_LINES`, matching the `PrimeEfficiencyScorer`
  baseline; the BE-DICT trained path shares `_assemble_window_outcome`'s computed flag.)
- [x] Test: a detector-less scorer reports `in_distribution = False`; the default design
  path computes OOD; the trained PRIDICT path is not less OOD-honest than its baseline.
  (`test_ensemble_without_detector_fails_honest_not_hardcoded_true`,
  `test_efficiency_ood_computed_from_cell_line_not_hardcoded`,
  `test_outcome_flags_ood_on_ambiguous_reagent` (prime),
  `test_outcome_flags_ood_on_ambiguous_spacer` (base).)

## 3. Trained-vs-heuristic legibility — DONE

- [x] Add a method value or boolean (e.g. `point_from_trained_model`) so a trained point
  estimate with an uncalibrated interval is distinguishable from a fully heuristic
  prediction using the honesty flags alone.
  (`Prediction.point_from_trained_model`; threaded through `calibrated_by` and `combine`.)
- [x] Set it on the trained scorers (Rule Set 3, PRIDICT2, BE-DICT, Lindel); leave it
  false on the heuristic baselines.
  (Set on `TrainedRuleSet3Scorer`, `PridictEngineAdapter`, and the BE-DICT trained path via
  `_assemble_window_outcome(from_trained=True)`. Lindel/cas9-outcome adapters return an
  `EditOutcome` distribution, not a scalar `Prediction`, so they carry no such flag.)
- [x] Test: a trained scorer and a heuristic scorer differ in the honesty surface without
  reading provenance.
  (`test_trained_point_is_distinguishable_from_heuristic`, `test_combine_ands_trained_flag`,
  `test_baseline_point_is_not_from_trained_model`, `test_trained_window_math_stamps_the_trained_flag`.)

## 4. Nominal vs measured interval level — DONE

- [x] Represent the fixed heuristic band as nominal/unmeasured — attach a note or use an
  `interval_level` sentinel — so a `calibrated = False` heuristic does not assert a
  specific measured coverage it never estimated.
  (`NOMINAL_INTERVAL_NOTE` attached to every fixed-band heuristic prediction: cas9
  baseline + trained RS3, prime efficiency + outcome, PRIDICT engine, base outcome.)
- [x] Ensure count-valued quantities (e.g. `bystander_burden`) do not claim an 80% band.
  (`COUNT_INTERVAL_NOTE` on `bystander_burden` via `_prediction(count_valued=True)`.)
- [x] Test: a heuristic prediction is flagged as carrying a nominal (not measured) interval
  width.
  (`test_heuristic_band_is_flagged_nominal_not_measured`.)

## 5. Regenerate goldens

- [x] Regenerate provenance/prediction goldens whose flags or levels change.
  (`scripts/reproduce_golden.json` re-derived — the menu now carries the honest notes;
  `docs/schemas` regenerated for the new `point_from_trained_model` field.)

## Status

All tasks are **shipped**. Task 2 — the last open piece — flipped the fail-open default to
fail-honest without making the design path uniformly OOD: each emitting scorer now derives
`in_distribution` from a documented check on its own inputs (a context/reagent N-and-length
check, or the cell-line membership the trained PRIDICT path shares with its baseline). Well-
formed reference inputs stay in-distribution, so no goldens churned; only genuinely
ill-formed (N-bearing / too-short) inputs now flag OOD. Ready to archive.
