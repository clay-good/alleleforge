# Readiness assessment — AlleleForge for the medical/research community

_Status as of 2026-09-05. Author: engineering audit. This file records the honest
state of the project so context is not lost across sessions. Sections dated
2026-06-23 are kept for the record; the 2026-09-05 update below supersedes their
numbers and the prime-efficiency row._

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
| Prime efficiency | **PRIDICT2.0** (`PridictEngineAdapter`) | sequence-level engine; golden-verified — but **not reachable from a `design()` menu** (see the 2026-09-05 update) |
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

---

## UPDATE 2026-09-05 — verified state, and one row corrected

**Gate, re-verified on this date:** `ruff` clean; `mypy --strict` clean (95 files);
**1,288 tests pass, 5 skipped, 97.6% coverage** (gate 85%); `mkdocs build --strict`
clean; `scripts/reproduce.py` matches golden; **4** example notebooks pass. (The
2026-06-23 figures — 906 tests, 93 files, 3 notebooks — are superseded.)

### Correction: prime efficiency is *not* usable from the CLI or `design()`

The table above lists three axes as "usable via `aforge design --trained-*`" and the
prime row as "sequence-level engine; golden-verified". The distinction is easy to
read past, so, plainly: **a `design()` menu's prime efficiency is the heuristic
baseline today, whatever weights are installed.** PRIDICT2 designs *and* scores its
own pegRNAs and exposes no "score this externally-supplied pegRNA" entry point, so
`PridictEngineAdapter` is a parallel path, not a `PrimeEfficiencyScorer`. The two
adapters that *do* implement that protocol (`DeepPrimeAdapter`, `GenETAdapter`)
raise `NotImplementedError` by design. `design()` now accepts a
`prime_efficiency_scorer` override, but nothing trained ships to pass it. Closing
this needs the per-pegRNA parity scorer tracked as **(P2)** in
[`pridict2-integration.md`](pridict2-integration.md), and a regression test
(`test_no_shipped_trained_prime_scorer_satisfies_the_override_protocol`) now fails
the moment one lands, so the docs saying "no trained prime scorer" cannot go stale
silently.

### Capability added since 2026-06-23

- **Prime editing designs the whole small-edit repertoire.** The RT template is
  built at variable length, so insertions, deletions, MNVs and delins enumerate
  alongside substitutions — previously the flagship could not design for any indel,
  CFTR ΔF508 included. Bounds: the replaced reference span ≤ `PRIME_MAX_EDIT` (44),
  the written allele ≤ `PRIME_MAX_TEMPLATED_EDIT` (29 = the RTT ceiling less the
  minimum 3' homology), both mirrored in routing.
- **Nuclease + HDR is routed as the explicit last resort** for a precise edit no
  break-free chemistry can reach (e.g. restoring a 41-base deletion), which
  previously returned an empty menu. Such a candidate carries its donor, is flagged
  `outcome-is-nhej-spectrum`, scores 0 on cleanliness (the honest number — the NHEJ
  spectrum contains no intended allele, and no HDR rate is invented), and the donor
  is emitted as an orderable ssODN.
- **The off-target scan is >10x faster** with byte-identical output, which also took
  the project's own test suite from ~299s to ~45s.

### The reputational guardrail, restated

Unchanged and still the governing constraint: **"population/haplotype-aware
off-target with honest uncertainty" is true today; "wraps PRIDICT2.0" is true only
of the parallel sequence-level engine, not of a ranked menu.** Everything the menu
reports for prime efficiency is labeled `HEURISTIC` / `calibrated=False`, and the
scorer now also states on each prediction that it has no edit-size feature.

### UPDATE 2026-09-05 (later the same day) — the CLI can now do what the README claims

A reachability sweep — take `design()`'s parameter list, check each against the CLI and the web API —
found that the project's **headline differentiator was library-only**. `design()` and `search()` have
always accepted a population database; **no CLI command could supply one**. `--populations` existed on all
three commands but names ancestry *labels* to stratify by and carries no alleles, so every command-line
scan was reference-only and returned an empty ancestry breakdown that reads as "no ancestry-specific risk
found". The README's own example even listed `--maf` among the tunable knobs while it filtered alleles
that were never loaded.

Now reachable from `design`, `batch` and `offtarget`: `--gnomad` (population allele frequencies),
`--haplotypes` (phased panel), `--patient-vcf` (personal variants), plus `--cell-context` (which raises the
OOD flag and was previously config-file-only on the CLI and absent from the web API entirely). Requesting
ancestries with no ancestry-bearing source now warns explicitly that the result is *unmeasured*, not clean;
an unreadable source is a data error rather than a silent reference-only fallback.

**Still library-only**, and worth knowing before promoting the CLI: `offtarget_regions` and
`encode_tracks`/`chromatin_track`. **Deliberately not exposed on the web API:** the three file inputs —
a client-supplied filesystem path is a server-side file-read primitive, so that surface needs server-side
configuration like the reference already has.

The guardrail above is unchanged and now actually holds at the command line: "population/haplotype-aware
off-target with honest uncertainty" is true today *and reachable by a user*, which it was not before.
