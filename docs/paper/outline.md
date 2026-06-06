# Methods preprint — outline

A working outline for the AlleleForge methods preprint. The first public release is
**v0.1.0** (three chemistries end to end with the benchmark); **v1.0.0** and the
full preprint are reserved for after external validation. This document is a
scaffold, not the manuscript.

> The scaffold below has been drafted into a manuscript: see the
> [**draft preprint**](preprint.md). The draft is honest about its maturity — the
> system, benchmark, and reproducibility apparatus are described as built, while
> the per-task accuracy numbers against published models are marked `[pending R1]`
> until the real-weights integration lands.

## Working title

*AlleleForge: variant-driven, multi-modality CRISPR edit design with calibrated
uncertainty and population-aware off-target analysis.*

## Abstract (claims to support)

1. A single variant-first interface returns a ranked menu spanning **nuclease,
   base, and prime editing**, each candidate carrying a calibrated efficiency
   interval, an outcome distribution, and a population/haplotype-aware off-target
   report — with complete provenance, reproducible from config + seed.
2. **Honest uncertainty is the product**: every numeric prediction is a calibrated
   interval with an out-of-distribution flag, never a bare point estimate.
3. **Population-aware safety**: off-target search over population variation by
   default, reported stratified by ancestry, reproduces the published
   reference-bias finding that a reference-only scan misses.
4. **CRISPR-Bench**: a frozen, calibration-first benchmark with cross-context
   splits is a field-level contribution valuable independently of the tool.

## 1. Introduction

- The fragmentation problem: efficiency, outcome, and off-target predictors are
  separate tools with incompatible inputs; no open tool unifies all four axes for
  prime editing.
- Two systematic gaps: point estimates without calibrated uncertainty, and
  reference-only off-target analysis that encodes reference bias.
- Contribution: one typed core wrapping published methods, plus the benchmark.

## 2. Methods

- **Domain model & provenance** (Phase 1): typed, validated vocabulary; the
  `Prediction[T]` uncertainty contract; the embedded provenance block.
- **Genome & variant front end** (Phases 2–4): bounds-checked reference access,
  content-addressed FM-index, build liftover with ambiguity flagging; left-aligned,
  reference-validated variant resolution from any input form.
- **Off-target engine** (Phase 5): reference, population, and haplotype-aware
  search; CFD / MIT / Cas12a-analog scoring behind one `OffTargetScorer` protocol;
  ancestry stratification.
- **Scoring substrate** (Phase 6): license-gated model zoo with mandatory model
  cards; swappable sequence-embedding backbone; deep-ensemble + conformal
  calibration; OOD detection.
- **Chemistries** (Phases 7–9): SpCas9 nuclease (efficiency + repair-outcome),
  base editing (window enumeration, bystander accounting), and prime editing
  (pegRNA/ngRNA enumeration, PE efficiency, byproduct prediction) — the flagship
  unifying all four axes.
- **Designer, reporting, interfaces** (Phases 10–13): routing and cross-chemistry
  ranking; cloning-ready oligos and reports; CLI and local web service over the
  same core.

## 3. CRISPR-Bench

- Five tasks (Cas9-efficiency, Cas9-outcome, BE-outcome, PE-efficiency,
  off-target-classification); fixed input/label contracts.
- Frozen, content-hashed, **cross-cell-type** splits; integrity verified on read.
- Metric battery with **ECE required on every task**; signed, provenance-stamped
  results; model-card-gated leaderboard.

## 4. Results (to be produced)

- End-to-end reproduction of the `rs114518452` reference-bias off-target case.
- Per-task benchmark numbers for the bundled scorers vs. the reference baseline,
  with calibration (ECE) reported alongside accuracy.
- Cross-context generalization gap (in-context vs. held-out-cell-type test folds).
- Ablations: ensemble size vs. interval calibration; with/without OOD flagging.

## 5. Discussion

- What honest uncertainty changes about how a design is selected and trusted.
- Why population-aware off-target is a safety requirement, not a feature.
- Limitations: cross-cell-type generalization is a field-wide reality; predictions
  are hypotheses requiring wet-lab validation.

## 6. Reproducibility & availability

- MIT-licensed code, schemas, and benchmark; pinned datasets/models with
  provenance; results re-derivable from config + seed.
- Zenodo DOI minted on the first tagged release; `CITATION.cff` provided.

## Key references

- DeWeirdt & Doench, *Nat Commun* 2022 (Rule Set 3).
- Allen et al., *Nat Biotechnol* 2019 (FORECasT); Shen et al., *Nature* 2018 (inDelphi).
- Arbab et al., *Cell* 2020 (BE-Hive); Mathis et al., *Nat Biotechnol* 2023 (PRIDICT2).
- Tsai et al., *Nat Biotechnol* 2015 (GUIDE-seq).
- Cancellieri, Pinello et al., *Nat Genet* 2023 (population-aware off-target / reference bias).
