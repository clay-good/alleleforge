# Cross-check models — definitive scope decision

_Status as of 2026-06-23. This resolves the remaining trained-adapter stubs._

## Decision

**AlleleForge supports exactly one verified real model per prediction axis.** Those
are now wired and golden-verified:

| Axis | Supported real model |
|---|---|
| SpCas9 efficiency | Rule Set 3 (`TrainedRuleSet3Scorer`) |
| Prime efficiency | PRIDICT2.0 (`PridictEngineAdapter`) |
| Base-edit outcome | BE-DICT (`BeDictAdapter`) |
| SpCas9 outcome | Lindel (`LindelAdapter`) |

The remaining trained adapters — `DeepPrimeAdapter`, `GenETAdapter`,
`InDelphiAdapter`, `XCrispAdapter`, `BeHiveAdapter` — are **out of supported
scope**. They remain as license-gated *placeholders* (the consent/card/gate flow is
still exercised), but their forward pass is intentionally not wired. Each was
investigated; none can be wrapped without violating AlleleForge's core principle —
*"reproducible to the byte; installs and passes anywhere; the heavy stack is opt-in"*
(README design principle 5; `SPEC_V2.md` R1). Wrapping a dependency-rotted or
framework-conflicting upstream would make a contributor unable to reproduce the gate.

## Per-model evidence (why each is out of scope)

| Adapter | Upstream | Blocker (investigated 2026-06-23) |
|---|---|---|
| `InDelphiAdapter` | inDelphi (Shen 2018) | TensorFlow 1.x / Theano era; not modern-Python-compatible. The MMEJ baseline already mirrors its mechanism. |
| `BeHiveAdapter` | BE-Hive (Arbab 2020) | TensorFlow 1.x era; rot risk; redundant with the wired BE-DICT on the same axis. |
| `XCrispAdapter` | X-CRISP (Seale 2025) | **GPL-3.0**; dual-framework (PyTorch **and** TF/Keras `.h5`); pins `scikit-learn==1.0.2` (no modern wheel) + `mpi4py` (needs an MPI runtime). Redundant with the wired Lindel. |
| `DeepPrimeAdapter` / `GenETAdapter` | DeepPrime via `genet` (Yu 2023) | `genet` **does install + import on Python 3.9** (verified), but the blocker is structural, not install: its **per-pegRNA** API (`DeepPrimeGuideRNA`) needs `target`/`edit_pos`/`edit_len`/`edit_type`, which `PegRNA` does **not** carry (the edit metadata lives in the resolved variant + reference, not the guide), so the `score(pegrna)` slot is unfillable from a `PegRNA` alone without threading edit context through the prime-scoring path. Its sequence-level API is redundant with the wired PRIDICT2.0 engine. Heavy stack (`tensorflow<2.10` + `viennarna`, Python ≤3.10) and redundant — out of scope. |

## Consequence / how the value they targeted is still served

- **Coverage:** every axis already has a real model — these add none.
- **Ensemble / inter-model agreement** (their only unique value): the
  `ensemble_outcome` machinery still works across the baseline + the wired real model
  per axis; a *second* real model per axis is the only thing it lacks, and no
  modern-Python-compatible second model exists for these axes today.

## Reversal criteria

Wire one only if a maintained, modern-Python-installable (or cleanly vendorable, like
the RS3 text-booster) release appears — then it follows the proven pattern (gate +
`real_weights` golden test + honest flags). Until then the adapters stay placeholders
and this decision stands.
