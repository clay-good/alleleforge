# Tasks

## 1. Make the calibrated flag unforgeable
- [x] 1.1 Route `calibrated=True` through a single constructor path only calibrators use
      (e.g. a private token, or a `Prediction.calibrated_by(...)` classmethod); default
      direct construction to `calibrated=False`.
- [x] 1.2 Update `ConformalCalibrator.calibrate` / `IsotonicCalibrator` to be the only
      producers of `calibrated=True`.
- [x] 1.3 Add a test that a scorer passing `calibrated=True` directly is rejected or
      coerced to `False`.

## 2. Couple OOD to the interval
- [x] 2.1 In `to_prediction` (and `Prediction` validation), forbid
      `in_distribution=False` together with `calibrated=True`.
- [x] 2.2 When `in_distribution=False`, widen the interval (or demote `method`) so an OOD
      prediction cannot present a narrow calibrated interval.
- [x] 2.3 Test: an ensemble with agreeing members on an OOD input yields a widened,
      uncalibrated prediction.

## 3. Mark the stub/heuristic path honestly
- [x] 3.1 When the backbone is the `StubEmbedder` (no real checkpoint), force
      `calibrated=False` and a heuristic-appropriate `method`.
- [x] 3.2 Test: `EnsembleEfficiencyScorer` on the stub reports `calibrated=False`.

## 4. Replace silent interval repair with a recorded note
- [x] 4.1 When `to_prediction` must widen an interval to contain the point, record a
      provenance/warning note instead of silently repairing.
- [x] 4.2 Test the note is emitted.

## 5. Make ranking uncertainty-aware
- [x] 5.1 In `design/ranking.py`, replace the bare `efficiency.value` projection with an
      uncertainty-discounted estimate: penalize `in_distribution=False` and/or rank OOD
      candidates on their lower interval bound.
- [x] 5.2 Surface each candidate's interval and OOD status in the score breakdown and the
      menu rationale.
- [x] 5.3 Test: an OOD candidate ranks below an otherwise-identical in-distribution one.

## 6. Reconcile goldens and docs
- [x] 6.1 Regenerate `scripts/reproduce.py` golden and any affected fixtures.
- [x] 6.2 Update README/docs describing the calibrated flag and uncertainty-aware ranking.
- [x] 6.3 `make ci` green; weight-free path unchanged in spirit.
