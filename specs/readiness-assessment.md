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

## What is NOT real yet (the gap)

Verified in code:

- `RuleSet3Scorer`, `PridictScorer`, `BaseEditOutcomePredictor` return
  `UncertaintyMethod.HEURISTIC` with `calibrated=False`. They are plausible-looking
  sigmoid stand-ins, **not** Rule Set 3 / PRIDICT2.0 / BE-Hive.
- The trained adapters (`DeepPrimeAdapter`, `BeHiveAdapter`, `GenETAdapter`, …)
  `raise NotImplementedError` on the forward pass.
- README four-axis table implies it "wraps PRIDICT2.0/BE-Hive". Today it does not.
- Benchmark accuracy-vs-published is marked `[pending R1]`; the shipped benchmark
  fixtures are **synthetic** (`"synthetic": true, "redistributable": false`) — the
  real validation libraries are not in the repo and are not redistributable.
- Model cards carry `checkpoint_sha256: null` (the open R0 item: pin real artifact
  hashes once upstream artifacts are frozen). The consent gate already refuses any
  `null`-hash *download* by design.

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
