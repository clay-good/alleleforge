# Readiness assessment — AlleleForge for the medical/research community

_Status as of 2026-06-23. Author: engineering audit. This file records the honest
state of the project so context is not lost across sessions._

## TL;DR

The **engineering** is production-grade. The **headline scientific value proposition
is not yet delivered**: the efficiency/outcome predictions are heuristic placeholders,
not the real published models the README compares against. Build scientific substance
*before* distributing (see [`distribution-plan.md`](distribution-plan.md)).

## What is real and usable today

- **Off-target nomination** (population/haplotype-aware). This is deterministic
  sequence matching + CFD/MIT matrix scoring — no ML weights involved. It runs on
  real genomes now and is the genuinely differentiated, trustworthy part. Promote
  this without caveats.
- **The framework itself**: typed core, honest uncertainty contract, reproducible-
  to-the-byte runs, content-addressed benchmark harness, consent/license/checksum
  model-zoo gate, CLI + web + native Rust parity. All verified green:
  - `ruff` clean; `mypy --strict` clean (93 files)
  - 906 tests pass, 1 skipped, **97.9% coverage** (gate 85%)
  - `mkdocs build --strict` clean; `scripts/reproduce.py` matches golden
  - 3 example notebooks pass; native crate builds, `cargo fmt`/`clippy` clean,
    35 parity tests pass
  - wheel + sdist build, `twine check` PASSED, assets bundled (py.typed, cards,
    splits, frontend)

## UPDATE 2026-06-23 — four real models now wired (one per axis)

The gap below has been substantially closed. Real, opt-in, parity-verified models
are now wired through the model-zoo gate (behind `real_weights`; CI stays weight-free):

| Axis | Real model | Status |
|---|---|---|
| Cas9 efficiency | **Rule Set 3** (`TrainedRuleSet3Scorer`) | bit-parity; **hosted** (auto-download) + usable via `aforge design --trained-efficiency` |
| Prime efficiency | **PRIDICT2.0** (`PridictEngineAdapter`) | sequence-level engine; golden-verified |
| Base-edit outcome | **BE-DICT** (`BeDictAdapter`) | golden-verified; position-mapping pinned |
| Cas9 outcome | **Lindel** (`LindelAdapter`) | golden-verified; usable via `aforge design --trained-outcome` |

Remaining stubs are documented optional **cross-checks** (each axis already has a
real model): `XCrispAdapter` (X-CRISP, 2025 PyTorch — feasible), `DeepPrimeAdapter`/
`GenETAdapter` (DeepPrime via the **PyPI** `genet` package — feasible),
`InDelphiAdapter` (2018 TF1/Theano — rot risk), `BeHiveAdapter` (2020 TF1 — rot
risk). See the per-axis specs. Their value is the inter-model **ensemble/agreement**
signal, not new coverage.

## What was NOT real (the original gap, now mostly closed)

Verified in code (pre-2026-06-23):

- `RuleSet3Scorer`, `PridictScorer`, `BaseEditOutcomePredictor` returned
  `UncertaintyMethod.HEURISTIC` with `calibrated=False` — sigmoid stand-ins. The
  baselines remain the weight-free defaults; the **real** models above are now the
  opt-in path.
- The trained adapters `raise NotImplementedError` — now wired for RS3, PRIDICT2,
  BE-DICT, Lindel; the rest remain documented cross-check stubs.
- Benchmark accuracy-vs-published is marked `[pending R1]`; the shipped benchmark
  fixtures are **synthetic** — real validation libraries are non-redistributable.
- Model cards carry `checkpoint_sha256: null` except `rule-set-3`, whose artifact is
  now pinned **and hosted** (R0 closed for that model).

## Reputational guardrail

Incumbents (CRISPOR, CHOPCHOP, Cas-OFFinder) are trusted. The first public claim
must be true and differentiated. **"Population/haplotype-aware off-target with honest
uncertainty" is true today. "Wraps PRIDICT2.0/BE-Hive" is not, yet.** Distributing a
tool that *looks* like it wraps those models but returns heuristics risks credibility.

## Minimum path to genuine scientific usefulness

1. Wire **one** real model end-to-end (chosen: **Rule Set 3** — see
   [`model-integration.md`](model-integration.md)).
2. Validate it (parity with the upstream package; published-Spearman reproduction is
   data-gated and documented as such).
3. Until each scorer is real, **relabel honestly** in README/UI as
   "heuristic baseline (real model pending)". Off-target needs no such caveat.

## Environment facts (this machine, 2026-06-23)

- Network: available (PyPI + GitHub reachable).
- ML stack: torch / transformers / scikit-learn / numpy **not** installed in `.venv`
  (core is deliberately light). Installable on demand.
- No GPU. CPU-only inference is fine for Rule Set 3 (LightGBM) and CPU PRIDICT2.
