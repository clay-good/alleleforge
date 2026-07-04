# Harden the honest-uncertainty contract end to end

## Why

"Honest uncertainty" is design principle 2 and the tool's central trust claim, but three
gaps let a confident-wrong answer pass as confident-right:

1. **`calibrated` is an unverified self-report.** Any scorer can set `calibrated=True`
   with no calibration having occurred; nothing cross-checks the flag
   (`types/prediction.py:62`). The default ensemble on the weight-free `StubEmbedder`
   reports `method=ENSEMBLE, calibrated=True` even though the stub is content-hashed
   noise, not a biological model (`scoring/cas9_efficiency.py:321-328`,
   `scoring/backbone.py:111-142`).
2. **The OOD flag is decoupled from interval width.** `in_distribution` is advisory
   (`types/prediction.py:50-51`); an ensemble whose members agree but are confidently
   wrong on an out-of-distribution input still gets a narrow interval
   (`scoring/uncertainty.py:126`). Nothing forces an OOD prediction to widen or demote.
3. **Ranking ignores uncertainty entirely.** The composite score uses only
   `efficiency.value` (`design/ranking.py:84`); the interval, `method`, `calibrated`, and
   especially `in_distribution=False` are not inputs. OOD survives only as a cosmetic
   flag (`design/prime.py:75-77`) with no score penalty — so an out-of-distribution or
   wide-interval prediction can outrank a calibrated, in-distribution one.

The result: the calibrated interval that the whole `uncertainty.py` machinery computes
does not actually change what the researcher is shown first.

## What Changes

- Make `calibrated=True` **unforgeable**: only a fitted calibrator may set it. A scorer
  constructing a `Prediction` directly gets `calibrated=False`; the flag becomes a real
  guarantee rather than a convention.
- **Couple OOD to the interval**: when `in_distribution=False`, a prediction may not also
  claim `calibrated=True`, and its interval is widened (or `method` demoted) so
  false-confidence is impossible by construction.
- Mark the **stub/heuristic path honestly**: a prediction produced without a real trained
  backbone reports `calibrated=False` (or a distinct method), so trust does not depend on
  reading provenance.
- Make **ranking uncertainty-aware**: rank on a calibration- and OOD-discounted estimate
  (e.g. the lower interval bound for OOD predictions, or an explicit OOD penalty), and
  surface the per-candidate uncertainty in the rationale.
- Replace `to_prediction`'s **silent interval repair** (a point outside its own interval
  is a broken-head signal) with a recorded provenance note.

This is a behavior-preserving hardening for correctly-calibrated scorers; it only changes
what happens for the paths that were over-claiming.

## Impact

- Specs: `uncertainty-contract` (MODIFIED honesty-flag semantics; ADDED OOD-width
  coupling), `candidate-ranking` (ADDED uncertainty-aware ordering).
- Code: `types/prediction.py`, `scoring/uncertainty.py`, `scoring/base.py`,
  `scoring/cas9_efficiency.py`, `scoring/base_outcome.py`, `scoring/prime_*`,
  `design/ranking.py`.
- Tests: new cases asserting the stub path is `calibrated=False`, OOD predictions cannot
  be `calibrated`, and an OOD candidate ranks below an otherwise-equal in-distribution
  one. Existing golden reproduce output will shift; regenerate the golden.
