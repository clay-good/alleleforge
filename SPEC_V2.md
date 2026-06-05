# AlleleForge — SPEC v2: post-v0.1.0 roadmap

`SPEC.md` is the v0.1.0 build contract and is **complete**: all fifteen phases are
implemented, the §16 definition-of-done is backed by an executable acceptance
suite, and CI is green across lint, type, test, docs, examples, and the Rust
crate (with a native↔Python FM-index parity run).

This document is the contract for what comes **after** v0.1.0 — the work to "bake"
the release: turning the swappable interfaces and weight-free stubs into pinned,
verified, real implementations, wiring the native kernels into the actual hot
paths, and earning the validation a v1.0 deserves. It uses the same structure as
`SPEC.md`: each phase lists **Context**, **Deliverables**, **Defaults &
decisions**, and **Tests**, and a phase is "done" only when its deliverables exist,
`ruff`/`mypy --strict` pass, CI is green, and its tests pass.

The guiding rule from `SPEC.md` still holds: when a decision is unspecified, prefer
the option that maximizes **reproducibility, honest uncertainty, and
population-aware safety — in that order**. Nothing here promises clinical
applicability; AlleleForge generates rigorously uncertain hypotheses.

## Sequencing

```
R0 (release hardening) ─┬─> R1 (real weights) ──> R5 (validation) ──> R6 (v1.0)
                        ├─> R2 (native kernels on hot paths)
                        └─> R3 (external adapters)
R4 (scale) draws on R1+R2 and feeds R5.
```

R0 gates a public v0.1.0. R1, R2, and R3 are independent and can proceed in
parallel once R0 lands. R5 (validation) needs R1. R6 (v1.0) needs R1 + R5.

Status legend: ☐ not started · ◐ in progress · ☑ done.

---

## R0 — Release hardening (gates the public v0.1.0)  ◐ in progress

**Context.** Everything required to cut a trustworthy `v0.1.0` that others can
install, reproduce, and cite. The code is done; this is the operational freeze.

**Deliverables.**
- **Pin every artifact.** Replace each `checkpoint_sha256: null` / dataset
  `sha256: null` with the real content hash of a frozen release artifact, so the
  consent-gated downloaders will actually fetch (an unverifiable artifact is
  refused by design). Record the pinned versions in `docs/data.md` and each model
  card. **(☐ blocked on freezing the real artifacts — the only remaining R0
  item; the gate already refuses a `null`-hash fetch.)**
- **Supply-chain (☑ landed).** Dependabot covers `pip` + `cargo` +
  `github-actions` (`.github/dependabot.yml`); a CI `security` job runs
  `pip-audit` + `cargo audit`; the release pipeline emits a CycloneDX SBOM
  (`sbom` job) and attaches it to the GitHub Release.
- **Reproducibility audit (☑ landed).** `scripts/reproduce.py` (and `make
  reproduce`) re-derives the canonical weight-free design run from config + seed,
  asserts run-to-run determinism, and diffs a canonicalized digest against a
  committed golden manifest; a CI `reproduce` job gates it.
- **Version bump** to `0.1.0` (drop `.dev0`) at tag time; confirm the
  `aforge_native` constant and `_version.py` agree.

**Defaults & decisions.** First public tag is **v0.1.0**; PyPI Trusted Publishing
+ multi-arch Docker + Zenodo DOI are already wired in `release.yml`. Artifacts are
pinned by content hash, never by mutable tag.

**Tests.** A test asserts no bundled card/descriptor ships a `null` hash once R0
closes; the reproduce target is exercised in CI against the stubs.

---

## R1 — Real-weights model integration  ◐ in progress

**Context.** v0.1.0 ships correct, swappable interfaces exercised by weight-free
stubs. R1 makes the real predictors load — through the **license-gated,
consent-required, checksum-verified** model zoo — so a user who opts in gets the
published models, with the checkpoint recorded in every result's provenance.

**Deliverables.**
- **Backbone download/consent flow (the first slice — landing with this spec).**
  Route `_HuggingFaceEmbedder` (Nucleotide Transformer v2 / Caduceus / Evo 2)
  through the model zoo instead of a bare `from_pretrained(model_id)`:
  - `ModelRegistry.authorize(name, *, use, consent)` — the license + consent gate
    for hub-resolved models, returning the provenance `ModelCheckpoint`.
  - `SequenceEmbedder.resolve_weights(...)` — uses `registry.checkpoint(...)` to
    fetch-and-checksum a pinned single artifact when the card pins a hash, else
    `authorize(...)`; records the resolved `ModelCheckpoint`. No consent ⇒
    `ConsentError`; wrong license-for-use ⇒ `LicenseError`; bad bytes ⇒
    `ChecksumError`. The whole flow is CI-tested with an **injected downloader**
    (no network, no torch); the actual tensor load stays `real_weights`-gated.
  - `model_checkpoint()` on the embedder so a scorer can stamp the backbone into
    provenance.
- **Shared weight gate (◐ landed).** One `model_zoo.loader.WeightGate` mixin
  implements the consent/license/checksum resolution for *every* trained model, so
  the flow lives in one place rather than per chemistry.
- **Per-chemistry real scorers**, each behind its card and the shared gate. The
  **consent/license/checksum resolution is wired for all of them** (◐); the
  trained **forward pass** over the loaded weights is the remaining step (needs
  the real weights / `real_weights`):
  - Cas9 efficiency: the backbone resolves through the gate; loading the fitted
    **Rule Set 3** coefficients + deep-ensemble heads is next.
  - Cas9 outcome: **inDelphi / Lindel / X-CRISP** adapters gated (◐); forward pass next.
  - Base-edit outcome: **BE-DICT / BE-Hive** adapters gated (◐); forward pass next.
  - Prime efficiency: **DeepPrime / GenET** adapters gated (◐); PRIDICT2.0 trained
    weights replace the heuristic next.
- **ONNX export** path (`export_onnx`) for the backbone, for portable inference.

**Defaults & decisions.** Default backbone stays **Nucleotide Transformer v2
(500M)**; it is **CC-BY-NC-SA** — loadable for research, refused for commercial
use by the license gate. Real weights are **never vendored**; they are fetched at
runtime with explicit consent and verified against the pinned card hash. The stub
path remains the CI default so the suite needs no weights.

**Tests.** Consent/license/checksum behavior is unit-tested with a fake downloader
(CI). Real embedding/scoring parity-vs-published-numbers tests are marked
`real_weights` (opt-in, skipped in CI). A provenance test asserts a real-backbone
scorer records the backbone `ModelCheckpoint`.

---

## R2 — Native kernels wired to the hot paths  ◐ in progress

**Context.** v0.1.0 ships the native **FM-index** (`bwt`) with a Python-parity
test, but it is opt-in and not yet on a production hot path. The spec layout also
reserves `kmer` and `haplotype` kernels. R2 implements them **and wires them into
the call sites that need them**, so the native build delivers real speedups — not
dead code.

**Deliverables.**
- **Sub-quadratic suffix-array construction (◐ landed).** `bwt.rs` now builds the
  suffix array by **prefix doubling** (`O(n log² n)`) instead of the direct sort's
  `O(n² log n)`, which collapsed on the long poly-A / poly-N runs real genomes
  contain. Output is byte-identical to the fallback (unique sentinel ⇒ unique SA),
  pinned by parity tests over low-complexity and random long inputs. **True-linear
  SA-IS** (`O(n)`) is the remaining optimization behind the same interface.
- **`kmer` kernel (◐ landed).** A native Rust k-mer kernel (`kmer.rs`) + pure
  -Python fallback (`offtarget._kmer`), wired into the off-target scan as a
  seed-and-extend prefilter (`scan_sequence(..., seed=...)`). It is a **proven
  superset** (pigeonhole: ≥1 uncut, substitution-free block of length
  `k = ⌊n/(E+1)⌋` survives any in-budget alignment), pinned by an exhaustive
  randomized seeded ≡ brute-force test. **Honest finding** from the R2
  micro-benchmark (`scripts/native_speedup.py`): the seed must run *before* the
  PAM check to prune, and it only pays off when selective (`k ≥ 5`, i.e. low edit
  budget) — measured ~2–4x there, a no-op at AlleleForge's default ≤4-mismatch+
  bulge budget (the seed is too short to prune). So it auto-engages only when
  `k ≥ 5`; the **FM-index seed-and-extend remains the genome-scale path** for the
  default budget.
- **FM-index wired into the reference scan (◐ landed).** The engine's stage-1
  reference search now runs FM-index seed-and-extend (`scan_sequence(...,
  use_fm_index=...)`): each concrete PAM is *located* in a content-addressed
  FM-index (the PAM is the seed) and only those anchors are *extended* by the
  shared alignment, replacing the linear `O(n)` PAM pass. It returns
  byte-identical hits to the brute-force scan (pinned by a randomized parity test
  on both the low-level scan and the engine report), and **auto-engages per
  region** past `FM_INDEX_AUTO_THRESHOLD` (1 Mb) so genome-scale contigs take the
  indexed path while small inputs stay on the linear scan. Building the
  whole-genome on-disk index via SA-IS at scale is the remaining R4 step.
- **`haplotype` kernel (◐ landed).** A native Rust haplotype-walk kernel
  (`haplotype.rs`: `haplotype_apply_variants`) + pure-Python fallback
  (`offtarget._haplotype`) wired into the haplotype off-target engine
  (`haplotype.py::_apply_all`): it materializes a common haplotype's
  alternative sequence by applying the haplotype's full variant set to the
  reference window (right-to-left so indels keep coordinates valid; a
  reference-base clash yields `None` and the engine skips it). It is
  byte-identical to the Python path — pinned by a fuzz parity test (lowercase
  refs, `N` bases, indels, overlaps, out-of-window positions) — and measures
  **~4x** in the R2 micro-benchmark. With this the three spec kernels
  (`bwt`/`kmer`/`haplotype`) are all on their hot paths behind the
  fallback-plus-parity discipline.
- A `bench/native_speedup.py` micro-benchmark recording native-vs-Python wall
  time per kernel (reported, not gated).

**Defaults & decisions.** Every native kernel keeps a **correct pure-Python
fallback** and a **parity test** pinning byte-identical results; `prefer_native`
selects it when built. The library never *requires* the crate.

**Tests.** Parity tests per kernel (native == Python) run in the CI `rust` job;
the off-target engine's existing tests run on both paths (fallback in the main
matrix, native in the rust job).

---

## R3 — External tool adapters  ◐ in progress

**Context.** Three `NotImplementedError` adapters were wired but inert:
`cas_offinder_adapter` (off-target cross-check), `variant/effect` VEP REST, and
the HGVS projection backend. R3 makes them real, behind the same consent/registry
discipline as data and models. **All three now have a real implementation behind
recorded-fixture tests** (◐ landed); only the live network/binary calls are
opt-in (`live_integration`-marked) and never run in CI.

**Deliverables.**
- **Cas-OFFinder** adapter (◐ landed): `format_input` builds the binary's input
  deck (spacer-`N`s + PAM pattern, query + mismatch budget); `parse_output` reads
  its results in **both** the legacy 6-column and bulge-aware 8-column layouts;
  `run(..., runner=...)` orchestrates write→invoke→parse with an **injectable
  runner**, so CI tests everything but the subprocess call itself, and
  disagreements are surfaced via the existing `disagreements()` cross-check.
- **VEP** consequence (◐ landed): `VepRestPredictor` issues the region-endpoint
  GET through an **injectable fetcher** and `parse_vep_response` maps the JSON to a
  `VariantEffect` (MANE/canonical or named-transcript selection, most-severe SO
  term, impact tier), with response **caching keyed by `(variant, assembly,
  transcript)`**. CI replays a recorded VEP response; only the live GET is opt-in.
- **HGVS** projection (◐ landed): `HgvsLibraryProjector` wraps the real `hgvs`
  library (UTA + SeqRepo, `AssemblyMapper.c_to_g`) behind the existing
  `HgvsProjector` interface; the import guard degrades to a clear `RuntimeError`
  when the optional library is absent (tested), and the live projection is opt-in.

**Defaults & decisions.** External tools are **optional**; their absence degrades
gracefully to the native engine with an explicit flag, never a crash. Network
calls require explicit opt-in and are cached.

**Tests.** Adapters are tested against **recorded fixtures** (no live network in
CI); a live-integration test is marked and opt-in.

---

## R4 — Scale & performance  ◐ in progress

**Context.** Make the genome-scale and cohort-scale paths real.

**Deliverables.**
- Whole-genome FM-index build + on-disk index for hg38 / T2T-CHM13 (driven by
  R2's SA-IS), with the memory-mapped query path validated at scale.
- **Cohort throughput (◐ landed).** `design.design_many(variants, ...)` streams a
  whole cohort through `design`: the input is **consumed lazily** (any iterable —
  a `cyvcf2` stream, a generator, a list) and only the per-item working set is
  held (each menu is summarized/optionally written to disk, then released), so
  peak memory does not grow with cohort size — pass `on_result` for a truly
  `O(1)` run. It is **resumable** via a JSONL run manifest (a re-run skips items
  already recorded) that opens with a provenance header, **isolates per-item
  failures** (an unresolvable variant is recorded, not fatal), and offers a
  thread-parallel path (`max_workers` + a `reference_factory`, since a pyfaidx
  handle is not thread-safe to share). The `cyvcf2` fast path and whole-genome
  scale validation remain.
- **Content-addressed cross-run caches (◐ landed).** A shared
  `alleleforge.cache.ContentAddressedCache` (sharded, atomically-written disk
  K/V under the cache dir) backs two cross-run memos: `CachedEmbedder.persistent`
  reuses embeddings across runs (scoped per backbone identity), and
  `OffTargetCache` (via `search(..., cache=...)`) reuses the reference scan. The
  off-target cache is **safety-gated** — used only for a reference-only search
  with the default scorer (no gnomAD/haplotype/patient augmentation, which the key
  cannot fully capture), so a stale entry can never be served for a danger scan.

**Defaults & decisions.** Streaming over materializing; bounded memory is a hard
requirement; every batch run emits a provenance manifest.

**Tests.** Scale tests run on a downsampled chromosome fixture in CI; full-genome
runs are an opt-in nightly.

---

## R5 — Validation, calibration, and the methods preprint

**Context.** The honesty claims must be earned on real data, not asserted.

**Deliverables.**
- Reproduce published efficiency/outcome numbers for each real scorer on its
  source benchmark split (R1), recorded as signed CRISPR-Bench results.
- **Calibration study:** measured ECE on real data per task; isotonic/conformal
  recalibration where intervals are miscalibrated; the cross-cell-type
  generalization gap quantified on the held-out-context splits.
- Fill in `docs/paper/outline.md` into a methods preprint with the R5 results.

**Defaults & decisions.** ECE is reported on every task (already enforced by
CRISPR-Bench); a scorer whose intervals are miscalibrated on real data is
recalibrated or shipped with the OOD flag dominant, never silently.

**Tests.** Benchmark runner produces signed, provenance-stamped result JSON for
each real scorer; leaderboard renders them; calibration figures regenerate from
a script.

---

## R6 — v1.0 release criteria

v1.0 is cut only when:
- Every shipped card/descriptor pins a real, verified artifact hash (R0).
- At least the Cas9-efficiency, PE-efficiency, and one outcome scorer load real
  weights through the consent/checksum flow and reproduce their published
  numbers within tolerance (R1 + R5).
- The native `bwt`/`kmer`/`haplotype` kernels are on their hot paths with parity
  tests and a recorded speedup (R2).
- Calibration (ECE) is measured on real data and intervals are calibrated or
  honestly flagged (R5); the cross-context generalization gap is documented.
- The methods preprint is posted and the Zenodo DOI minted (R5 + R0).

Until then the public release stays **v0.1.0**: three chemistries end to end with
honest uncertainty and the benchmark, baked but not yet externally validated.

---

*This document extends `SPEC.md`. When v2 and v1 disagree, v2 wins for post-1.0
work; otherwise `SPEC.md` remains the contract for the shipped surface.*
