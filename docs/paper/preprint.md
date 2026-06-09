# AlleleForge: variant-driven, multi-modality CRISPR edit design with calibrated uncertainty and population-aware off-target analysis

**Methods preprint — draft (v0.1.0).** This is the manuscript draft that the
[working outline](outline.md) scaffolds. It is **honest about its own maturity**:
the system, the benchmark, and the reproducibility apparatus are complete and
described here as built; the per-task accuracy numbers against published models
are reserved for after the real-weights integration (SPEC v2 round R1) and external
validation (R5), and every such pending result is marked **[pending R1]** below.
Nothing here is a clinical claim. AlleleForge generates rigorously uncertain
hypotheses that require wet-lab validation.

*Clay Good. Correspondence: hi@claygood.com. Code, schemas, and benchmark:*
*<https://github.com/clay-good/alleleforge> (MIT-licensed).*

---

## Abstract

CRISPR edit design is fragmented across single-axis tools: efficiency, repair
outcome, and off-target predictors are separate programs with incompatible inputs,
and no open tool unifies all four axes for prime editing. Two systematic gaps cut
across the field — predictions are reported as point estimates without calibrated
uncertainty, and off-target analysis is run against a single reference genome,
encoding a reference bias that is blind to variation a real patient carries.

AlleleForge is a typed Python core that takes a **variant** as its primary input
and returns a single ranked menu spanning **nuclease, base, and prime editing**.
Every candidate carries (i) a **calibrated predictive interval** with an
out-of-distribution flag rather than a bare float, (ii) an outcome distribution,
and (iii) a **population- and haplotype-aware** off-target report stratified by
ancestry, with complete provenance and run-to-run reproducibility from config plus
seed. Alongside the tool we release **CRISPR-Bench**, a frozen, calibration-first
benchmark whose cross-cell-type test folds measure generalization rather than
memorization, and on which Expected Calibration Error (ECE) is a required metric
on every task. We reproduce the published reference-bias finding end to end: a
reference-only scan returns zero off-targets for a locus where a minor allele
creates a high-CFD, ancestry-enriched off-target that the population-aware scan
nominates. The split-conformal recalibration layer restores nominal interval
coverage with a finite-sample guarantee. AlleleForge is MIT-licensed; real model
weights are never vendored — they are fetched at runtime under a license- and
consent-gated, checksum-verified registry.

---

## 1. Introduction

**The fragmentation problem.** Designing a CRISPR edit for a specific variant
requires answers on four axes: *which* chemistry can make the edit, *how
efficiently* a given guide or pegRNA will act, *what distribution of outcomes* the
edit produces (precise correction versus byproducts and bystanders), and *where
else* in the genome the reagent might cut. In practice each axis is served by a
separate tool — Rule Set 3 or DeepHF for nuclease efficiency, inDelphi/FORECasT/
Lindel for repair outcome, BE-Hive/BE-DICT for base-edit outcome, DeepPrime/
PRIDICT2 for prime efficiency, Cas-OFFinder/CRISPRitz for off-target enumeration —
with incompatible input contracts and no shared notion of uncertainty. For prime
editing in particular, no open tool unifies all four axes behind one interface.

**Two systematic gaps.** First, the field reports **point estimates**. A guide
predicted at efficiency 0.7 and a guide predicted at 0.7 ± 0.4 are presented
identically, even though only one is a defensible ranking signal. Second,
off-target analysis is conventionally run against **one reference genome**. A
patient is not the reference: a minor allele can destroy a predicted off-target or,
worse, *create* a new one with a high cutting score. Reference-only analysis
silently encodes this bias, and the bias is ancestry-structured because allele
frequencies are.

**Contribution.** AlleleForge is one typed core that (a) wraps published
single-axis methods behind swappable, uncertainty-carrying interfaces; (b) makes
the variant — not a pre-chosen guide — the entry point, so chemistry routing and
cross-chemistry ranking happen inside the tool; (c) treats population variation as
a first-class off-target input; and (d) ships CRISPR-Bench, a calibration-first
benchmark that is useful independently of the tool. The design rule throughout,
inherited from the build spec, is: when a decision is unspecified, prefer the
option that maximizes **reproducibility, honest uncertainty, and population-aware
safety — in that order**.

## 2. Methods

### 2.1 Domain model and provenance

The core is a typed, validated vocabulary (`pydantic` models): sequences, variants,
guides, edits, candidates, and predictions. Two invariants are structural rather
than conventional.

- **The uncertainty contract.** No scorer returns a bare float. Every efficiency
  or outcome prediction is a `Prediction[T]` carrying a point estimate, a
  calibrated predictive `interval` (default **80%**, stored with its level), the
  `method` that produced it, an `in_distribution` flag, and a `calibrated` flag.
  For numeric payloads the point estimate is required to lie inside the interval;
  structured payloads (e.g. an outcome distribution) carry an interval over a
  derived scalar. `Prediction.combine` propagates the honesty flags conservatively
  — a combination is `calibrated` only if every input was, and `in_distribution`
  only if every input was.
- **Embedded provenance.** Every result carries a provenance block recording the
  inputs, config, seed, dataset and model checkpoints (by content hash), and
  software version, so a result is reproducible and auditable from its own record.

### 2.2 Genome and variant front end

Reference access is bounds-checked and build-aware (`pyfaidx`-backed, with a
weight-free in-memory reference for tests). Coordinates are projected across builds
by liftover with explicit **ambiguity flagging** rather than silent best-guess
mapping. Variant resolution accepts any input form — HGVS `g./c./p.`, VCF-style,
rsID (dbSNP), or a ClinVar accession — and normalizes it to a single validated
`Variant`: indels are **left-aligned**, and the asserted reference base is
validated against the build (a mismatch is a hard error, the usual signature of a
wrong-build input). Genome-scale string search is served by a content-addressed
**FM-index**; the persistent, memory-mapped whole-genome variant (`GenomeIndex`)
builds one index per contig and both strands and survives across runs.

### 2.3 Off-target engine

A single `OffTargetScorer` protocol sits over three specificity scores: **MIT/Hsu**
(exact published 20-position weight table), **CFD** (published PAM table; mismatch
weights default to a transparent seed model and are injectable with the exact
Doench matrix), and a **CFD-Cas12a analog** (PAM-proximal 5' seed, `TTTV` PAM). The
engine searches three site origins:

1. **Reference** — FM-index seed-and-extend (each concrete PAM is *located* in the
   index and only those anchors are *extended* by the shared alignment), which
   auto-engages on contigs above a 1 Mb threshold and is byte-identical to the
   linear brute-force scan (pinned by a randomized parity test).
2. **Population** — variants from gnomAD (and equivalents) are applied so that
   off-targets *created or destroyed by* common variation are searched, not just
   the reference sequence.
3. **Haplotype** — common haplotypes are materialized and scanned, since linked
   variants interact.

Population off-targets are reported **stratified by ancestry**; the engine surfaces
the worst-ancestry score rather than averaging it away. External tools (Cas-OFFinder)
are integrated as an optional **cross-check** behind an injectable runner;
disagreements are reported as flags, never silently dropped.

### 2.4 Scoring substrate

Trained predictors load through a **license-gated model zoo**: every model declares
a mandatory model card (name, license, citation, intended use, training context,
and a pinned checkpoint hash), and resolution runs through one shared `WeightGate`
that enforces consent, checks the license against the requested use, and verifies
the downloaded bytes against the card hash before any tensor is loaded. Real weights
are **never vendored**; the CI default is a weight-free stub path so the entire
suite runs without downloads, network, or a scientific stack.

A swappable `SequenceEmbedder` backbone (default **Nucleotide Transformer v2
(500M)**, CC-BY-NC-SA — loadable for research, refused for commercial use by the
license gate) feeds the chemistry scorers. Uncertainty is produced by the
`alleleforge.scoring.uncertainty` module (pure stdlib, hence CI-exercised on the
stub):

| Method | Role | Interval construction |
|---|---|---|
| **Deep ensemble** (default, N=5) | production path | Gaussian band `mean ± z·σ` from member **disagreement**, which widens automatically on OOD inputs |
| **Evidential** | single-model fallback | Normal-Inverse-Gamma head splitting **aleatoric** from **epistemic** variance |
| **Quantile** | model emits quantiles | read off the `(1±level)/2` quantiles directly |

Post-hoc **isotonic calibration** maps raw probabilities to calibrated ones; its
regression analog, **split-conformal recalibration** (§2.6), corrects interval
*width*. Out-of-distribution detection is not guesswork: an `OODDetector` stores a
training-set reference in embedding space and flags any input whose nearest-reference
distance exceeds a density-derived threshold — a prime-editing target outside
PRIDICT's HEK293T/K562 training context is flagged rather than silently scored.

### 2.5 Chemistries

Three chemistries are implemented end to end behind a common enumerate → score →
off-target → rank pipeline.

- **SpCas9 nuclease.** Guide enumeration over `NGG` PAMs; efficiency scoring
  (Rule Set 3 substrate) and a repair-outcome distribution (inDelphi/FORECasT/
  Lindel substrate).
- **Base editing (ABE/CBE).** Editing-window enumeration with explicit **bystander
  accounting** — every C (CBE) or A (ABE) in the activity window is a potential
  co-edit, and the outcome model reports the bystander distribution, not just the
  on-target conversion.
- **Prime editing — the four-axis flagship.** pegRNA and nicking-guide enumeration
  (PBS/RT-template design), PE efficiency (DeepPrime/PRIDICT2 substrate), and
  byproduct prediction, unifying all four axes for the one chemistry that most
  needs it.

### 2.6 Conformal interval recalibration

`ConformalCalibrator` learns a single multiplicative width scale from a held-out
calibration set so the recalibrated intervals meet a target coverage with the
finite-sample **split-conformal guarantee**: on exchangeable data the truth falls
inside the interval with probability at least `level`. Because the scale multiplies
each interval's half-width, the model's *relative* per-example uncertainty (wider
where it is less sure) is preserved and only the global width is corrected.
`empirical_coverage` measures whether a set of intervals needs recalibration. A
scorer measured miscalibrated is recalibrated or shipped with its OOD flag dominant,
never silently.

### 2.7 Designer, reporting, and interfaces

The **designer** takes a resolved variant, routes it to the chemistries that can
make the edit, enumerates and scores candidates per chemistry, runs the off-target
engine, and produces a single **cross-chemistry ranking**. Output is
cloning-ready: oligo sequences and a structured report rendered as HTML/PDF/JSON/
TSV, each accompanied by a provenance sidecar. The same core is exposed through an
`aforge` CLI (Typer) and a local FastAPI web service, including a cohort endpoint;
**cohort-scale** design streams an entire VCF through a resumable, bounded-memory
run that isolates per-item failures and emits a provenance manifest.

### 2.8 Native acceleration

Three hot paths have native Rust kernels behind a **correct pure-Python fallback**
and a **byte-identical parity test**, so the library never *requires* the crate and
CI never blocks on the native build: an FM-index (`bwt`, built by linear-time
**SA-IS** suffix-array construction), a seed-and-extend `kmer` prefilter (a proven
pigeonhole superset, auto-engaged only when selective), and a `haplotype`-walk
kernel that applies a haplotype's full variant set to a reference window
(right-to-left so indels keep coordinates valid). The microbenchmark records ~4×
for the haplotype kernel and 2–4× for the k-mer prefilter where it is selective;
the FM-index seed-and-extend is the genome-scale path at the default edit budget.

## 3. CRISPR-Bench

CRISPR-Bench is a calibration-first benchmark released alongside the tool and
valuable independently of it: versioned datasets, frozen splits, fixed task
contracts, and a model-card-gated leaderboard that any model can be measured
against.

**Five tasks**, each with a fixed input/label contract and a primary metric, plus
**ECE required on every task**:

| Task | Kind | Source corpus | Primary | + required |
|---|---|---|---|---|
| `cas9-efficiency` | regression | Rule Set 3 validation (DeepHF/DeepSpCas9) | Spearman | Pearson, **ECE** |
| `cas9-outcome` | distribution | FORECasT, inDelphi, Lindel | KL ↓ | top-1, **ECE** |
| `be-outcome` | distribution | BE-Hive, BE-DICT | KL ↓ | top-1, **ECE** |
| `pe-efficiency` | regression | PRIDICT2 Library-Diverse | Spearman | Pearson, **ECE** |
| `offtarget-classification` | classification | GUIDE-seq / CHANGE-seq aggregates | AUROC | AUPRC, **ECE** |

**Frozen, content-hashed, cross-context splits.** A split is immutable once
published. Each split file pins fold membership and two hashes — one of the dataset
content it was cut from (so a frozen split is invalidated the instant a label
changes underneath it) and one of the split's own membership (so the file cannot be
silently edited). `load_split()` recomputes and verifies **both** on read. The test
folds deliberately hold out a whole cell type / chromatin context, so the benchmark
measures **generalization**, not memorization — cross-cell-type generalization
being a known weak spot of guide models.

**Honest leaderboard.** Each run returns a **signed, provenance-stamped**
`BenchmarkResult`; a submission must carry a model card (name, license, citation
mandatory), and the board re-verifies every signature, rejecting unsigned, edited,
or uncarded entries. The split version is shown next to every score so cross-version
numbers are never silently mixed. Committed fixtures are **synthetic stand-ins**
(`synthetic: true`, `redistributable: false`) so the benchmark runs in CI with no
downloads; the loader for real corpora goes through the same consent-gated registry
as the rest of the system.

## 4. Results

### 4.1 Available now (weight-free, end to end)

**Reference bias, reproduced.** The canonical cautionary case is the BCL11A
enhancer variant `rs114518452` (Cancellieri, Pinello et al., *Nat Genet* 2023). On a
locus reproducing the mechanism, a **reference-only** scan returns **zero**
off-targets, while the **population-aware** scan nominates the high-CFD off-target
that the minor allele creates — reported ancestry-stratified with its
African-ancestry-enriched frequency (AFR ≈ 0.105 here) preserved rather than
averaged into an overall figure. This is an executable integration test, not a
narrative claim; it requires no model weights because it exercises the off-target
engine and the population layer directly.

![Reference-only scan finds zero off-targets where the population-aware scan nominates one high-CFD site.](../assets/figures/reference_bias.svg)

**Split-conformal recalibration restores coverage.** On a deliberately
under-covering interval set (seeded, synthetic), the recalibration layer restores
nominal coverage with its finite-sample guarantee, regenerated by
`scripts/calibration_study.py`:

| Target level | Raw coverage | Recalibrated coverage | Width scale |
|---:|---:|---:|---:|
| 0.80 | 0.193 | 0.801 | 5.15 |
| 0.90 | 0.193 | 0.914 | 6.89 |

The recalibrated coverage meets the target at both levels; the single width scale
preserves relative per-example uncertainty.

![Raw coverage near 19% rises to the nominal 80%/90% target after split-conformal recalibration.](../assets/figures/conformal_coverage.svg)

**Calibration and generalization machinery.** Every CRISPR-Bench task reports its
ECE, and the cross-cell-type generalization gap is quantified per task. The values
below verify the *machinery* on the weight-free splits (real numbers await §4.2);
the figures regenerate byte-for-byte from `scripts/figures.py`.

![Per-task ECE across the five CRISPR-Bench tasks, with the miscalibration flag threshold.](../assets/figures/task_ece.svg)

![Per-task cross-cell-type generalization gap, oriented so positive means worse generalization.](../assets/figures/generalization_gap.svg)

**Determinism.** The canonical design run is re-derived from config plus seed and a
canonicalized digest is diffed against a committed golden manifest
(`scripts/reproduce.py`, gated in CI), so the reproducibility claim is enforced, not
asserted.

> **Plumbing, not science.** The per-task metric values produced by the committed
> synthetic fixtures (e.g. baseline Spearman, KL, AUROC, and ECE in the calibration
> report) verify the *machinery* — the metric battery, the cross-context split
> mechanics, and the generalization-gap computation — and are explicitly **not**
> model-quality results. Real numbers require real weights (§4.2).

### 4.2 Pending real-weights integration (R1) and external validation (R5)

The following are reserved until the per-chemistry scorers load their published
weights through the consent/checksum flow, and are **not** claimed here:

- **[pending R1]** End-to-end reproduction of published efficiency/outcome numbers
  for each real scorer on its source benchmark split, recorded as signed
  CRISPR-Bench results.
- **[pending R1]** Per-task accuracy versus the reference baseline with measured
  ECE *on real data* reported alongside accuracy.
- **[pending R1]** The cross-cell-type generalization gap **on real predictions**.
  The gap machinery and table regenerate now on the weight-free cross-context
  splits; only the real-data values await R1.
- **[pending R1]** Ablations: ensemble size versus interval calibration; with and
  without OOD flagging.

## 5. Discussion

**What honest uncertainty changes.** A calibrated interval changes selection, not
just presentation. Two candidates with the same point estimate but different
interval widths are different recommendations; an OOD-flagged candidate is a
prompt to validate before trusting, not a number to rank blindly. Making the
interval and the flag structural — a scorer *cannot* return a bare float — moves
honesty from a reporting convention to an invariant.

**Why population-aware off-target is a safety requirement.** The reference-bias
case is not an edge case dressed up as one: allele frequencies are
ancestry-structured, so a reference-only pipeline has ancestry-structured blind
spots. Searching population and haplotype variation by default, and reporting the
worst ancestry rather than the mean, treats this as the safety requirement it is.

**Limitations.** Cross-cell-type generalization is a field-wide reality, not a
solved problem; CRISPR-Bench makes it the headline split precisely so it is not
hidden. All predictions are hypotheses requiring wet-lab validation. AlleleForge is
a research tool — not a medical device and not medical advice — and the v0.1.0
release is explicitly **baked but not yet externally validated**: three chemistries
end to end with honest uncertainty and the benchmark, with the published-number
reproductions reserved for v1.0 after R1 and R5.

## 6. Reproducibility and availability

Code, schemas, and the benchmark are **MIT-licensed** and public. Datasets and
models are pinned with provenance and fetched under a license- and consent-gated,
checksum-verified registry — never vendored. Results are re-derivable from config
plus seed, and a CI reproducibility job enforces run-to-run determinism against a
golden manifest. Supply-chain hardening (Dependabot across pip/cargo/actions, a
`pip-audit` + `cargo audit` CI job, and a CycloneDX SBOM attached to each release)
and a `CITATION.cff` ship with the repository; a Zenodo DOI is minted on the first
tagged release.

## Key references

- DeWeirdt & Doench, *Nat Commun* 2022 (Rule Set 3).
- Allen et al., *Nat Biotechnol* 2019 (FORECasT); Shen et al., *Nature* 2018 (inDelphi); Chen et al., *Nucleic Acids Res* 2019 (Lindel).
- Arbab et al., *Cell* 2020 (BE-Hive); Marquart et al., *Nat Commun* 2021 (BE-DICT).
- Mathis et al., *Nat Biotechnol* 2023 (PRIDICT2); Kim et al., *Cell* 2021 (DeepPrime).
- Doench et al., *Nat Biotechnol* 2016 (CFD); Hsu et al., *Nat Biotechnol* 2013 (MIT specificity).
- Tsai et al., *Nat Biotechnol* 2015 (GUIDE-seq).
- Cancellieri, Pinello et al., *Nat Genet* 2023 (population-aware off-target / reference bias).
- Dalla-Torre et al., 2023 (Nucleotide Transformer); Lakshminarayanan et al., *NeurIPS* 2017 (deep ensembles); Angelopoulos & Bates, 2023 (conformal prediction).

---

*This draft accompanies AlleleForge v0.1.0. The complete preprint — with the §4.2
real-data results — is reserved for the v1.0 release after the real-weights
integration (R1) and the validation round (R5). See
[`SPEC_V2.md`](https://github.com/clay-good/alleleforge/blob/main/SPEC_V2.md) for the
round definitions and [the outline](outline.md) for the section scaffold.*
