# Compute honest uncertainty, don't assert it

## Why

A prior change (`harden-uncertainty-honesty`, archived) made ranking *respect* the
`calibrated`/`in_distribution` flags and coupled a set OOD flag to interval width. But the
flags themselves are still, in the default paths, either **hardcoded**, **unwired**, or
**placeholder** — so the honesty contract is enforced on values that were never honestly
computed:

1. **OOD widening has no absolute floor.** `uncertainty.py:87-89` widens an OOD interval
   multiplicatively (`half *= 2.0`). When ensemble members agree, `std == 0` → `half == 0`,
   and `0 * 2 == 0`: an out-of-distribution input can still present a **zero-width,
   maximally confident** interval — exactly what the spec's "never narrow even when members
   agree" clause forbids (`uncertainty-contract` spec, "OOD predictions widen, never narrow").
2. **The OOD detector is never wired into any default scorer.** `OODDetector`
   (`uncertainty.py:477-521`) is implemented and tested but has **zero construction sites**
   in production; the default `EnsembleEfficiencyScorer` runs with `ood=None` and returns
   `in_distribution = True` unconditionally (`cas9_efficiency.py:344`, `design/cas9.py:146`).
   `prime_outcome.py:73`, `base_outcome.py:157`, and — worst — the real trained
   `pridict_engine.py:134` all hardcode `in_distribution = True`, so the trained PRIDICT2
   path is *less* OOD-honest than the heuristic baseline it replaces (which at least checks
   the cell context, `prime_efficiency.py:101`). The OOD flag conveys no information where
   it matters most: primary cells and unusual sequence contexts.
3. **A trained prediction is indistinguishable from a heuristic by its flags.** The real
   LightGBM Rule Set 3 model returns `method = heuristic, calibrated = False`
   (`cas9_efficiency.py:253-255`) — byte-identical honesty flags to the pure heuristic
   baseline (`cas9_efficiency.py:117-119`); PRIDICT2, BE-DICT, and Lindel adapters do the
   same. The spec promises a heuristic-vs-trained distinction "without reading provenance,"
   but today the single tag a consumer is told to rely on cannot separate a trained point
   estimate from a rule-of-thumb.
4. **A fixed ±0.15 band asserts a fabricated 80% coverage.** A single constant
   `_INTERVAL_HALF = 0.15` is stamped as `interval_level = 0.80` everywhere
   (`cas9_efficiency.py:111`, `base_outcome.py:154`, `prime_efficiency.py:104`, …),
   including on an unbounded count (`bystander_burden`, `base_outcome.py:150-159`). A
   constant half-width cannot be an 80% predictive interval, and nothing distinguishes a
   *nominal placeholder* level from a *measured* one — a consumer thresholding on
   `interval_level` is misled.

## What Changes

- **Add an additive minimum half-width floor** to OOD widening, so any
  `in_distribution = False` prediction is strictly wider than any in-distribution interval
  the same head could emit and a zero-width interval never survives OOD flagging.
- **Require scorers to compute `in_distribution`** from an explicit distribution check; a
  scorer with no detector wired SHALL default `in_distribution = False` (fail-honest),
  never `True`. Ship a reference/detector on the default ensemble, prime, and base scorers
  so OOD is actually computed — and give the trained PRIDICT/BE-DICT/Lindel paths at least
  the OOD honesty of their heuristic baselines.
- **Distinguish a trained point estimate from a heuristic** in the honesty surface without
  reading provenance (a method value or a boolean like `point_from_trained_model`).
- **Stop asserting a measured coverage level for an unmeasured heuristic band** — represent
  the fixed spread as nominal/unmeasured (a note or an `interval_level` sentinel) so a
  placeholder width never masquerades as measured coverage.

## Impact

- Specs: `uncertainty-contract` (MODIFIED OOD widening floor; ADDED computed-OOD
  requirement, trained-vs-heuristic legibility, nominal-vs-measured interval level).
- Code: `scoring/uncertainty.py`, `scoring/cas9_efficiency.py`, `scoring/prime_efficiency.py`,
  `scoring/prime_outcome.py`, `scoring/base_outcome.py`, `scoring/pridict_engine.py`,
  `types/prediction.py` (method/flag surface), and the default scorer wiring in `design/`.
- Tests: an OOD input with perfectly-agreeing members gets a non-zero-width interval; a
  detector-less scorer returns `in_distribution = False`; a trained scorer is
  distinguishable from a heuristic by flags alone; a heuristic prediction does not assert a
  measured 80% level. This changes some emitted flags/levels — regenerate affected goldens.
