# Tasks

## 1. OOD widening floor — DONE

- [x] In `scoring/uncertainty.py`, add an additive minimum half-width floor to the OOD
  widening path so the interval is strictly wider than any in-distribution interval the
  same head could produce, and a zero-width interval cannot survive OOD flagging.
  (`OOD_MIN_HALF_WIDTH = 0.05`, added on top of `OOD_WIDEN_FACTOR` in `to_prediction`.)
- [x] Test: an OOD prediction whose ensemble members agree exactly (`std == 0`) returns a
  non-zero-width interval and `calibrated = False`.
  (`test_ood_floor_defeats_zero_width_agreement`.)

## 2. Compute in_distribution; fail honest by default

- [ ] Change every scorer that emits a `Prediction` (`cas9_efficiency.py`,
  `prime_efficiency.py`, `prime_outcome.py`, `base_outcome.py`, `pridict_engine.py`) to
  derive `in_distribution` from an explicit distribution check; a scorer with no detector
  SHALL default `in_distribution = False`, never `True`.
- [ ] Wire a training reference + `OODDetector` (or a documented context check) into the
  default ensemble, prime, and base scorers used by `design/`.
- [ ] Give the trained PRIDICT/BE-DICT/Lindel adapters at least the OOD check their
  heuristic baselines already apply (e.g. cell-context membership).
- [ ] Test: a detector-less scorer reports `in_distribution = False`; the default design
  path computes OOD; the trained PRIDICT path is not less OOD-honest than its baseline.

## 3. Trained-vs-heuristic legibility

- [ ] Add a method value or boolean (e.g. `point_from_trained_model`) so a trained point
  estimate with an uncalibrated interval is distinguishable from a fully heuristic
  prediction using the honesty flags alone.
- [ ] Set it on the trained scorers (Rule Set 3, PRIDICT2, BE-DICT, Lindel); leave it
  false on the heuristic baselines.
- [ ] Test: a trained scorer and a heuristic scorer differ in the honesty surface without
  reading provenance.

## 4. Nominal vs measured interval level

- [ ] Represent the fixed heuristic band as nominal/unmeasured — attach a note or use an
  `interval_level` sentinel — so a `calibrated = False` heuristic does not assert a
  specific measured coverage it never estimated.
- [ ] Ensure count-valued quantities (e.g. `bystander_burden`) do not claim an 80% band.
- [ ] Test: a heuristic prediction is flagged as carrying a nominal (not measured) interval
  width.

## 5. Regenerate goldens

- [ ] Regenerate provenance/prediction goldens whose flags or levels change.
