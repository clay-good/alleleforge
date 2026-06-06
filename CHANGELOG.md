# Changelog

All notable changes to AlleleForge are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). The
project is in the `0.x` series until the three launch modalities pass
acceptance.

## [Unreleased]

### Added

- **Phase 0 — Repository bootstrap.** Hatchling build, `aforge` console-script
  entry point, dependency groups (`core`/`genome`/`variant`/`ml`/`web`/`docs`/`dev`),
  pinned tool configuration (ruff line-length 100; mypy `strict`; pytest with an
  85% coverage gate). Rust PyO3 crate `aforge_native` (built with maturin)
  exposing `version()` to prove the toolchain end to end. Single-source version
  in `_version.py`; typed `Settings` (pydantic-settings) carrying every
  cross-cutting default (seed `20240501`, reference `hg38`, 80% interval level,
  MAF threshold `0.001`, XDG cache dir). MIT license for all code, schemas,
  benchmark, and first-party weights; `CITATION.cff`, Contributor
  Covenant 2.1 code of conduct, contributing guide, multi-stage `Dockerfile`,
  `docker-compose.yml` stub, conda environment file, and a GitHub Actions CI
  matrix (lint, type-check, test, strict docs build).
- **Phase 1 — Core domain types & schemas.** The typed vocabulary under
  `alleleforge.types`: strand-aware `DNASequence` with ambiguity-aware
  reverse-complement, `GenomicInterval` (0-based half-open), `Variant` with
  idempotent normalization, guide/pegRNA/nicking-guide models with structural
  validation, edit-outcome and strategy models, off-target site/report models
  with ancestry stratification, the generic `Prediction[T]` uncertainty
  contract (80% interval, method tag, in-distribution and calibration flags),
  design-candidate and ranked-menu models, and the provenance block. JSON
  Schemas for every public model are emitted to `docs/schemas/`.
- **Phase 2 — Genome access & indexing.** `alleleforge.genome`: a strand-aware,
  bounds-checked `ReferenceGenome` over pyfaidx that N-pads contig ends and
  flags the over-run rather than crashing, with a registry of built-in builds
  (hg38, T2T-CHM13 v2, mm39) and consent-gated, checksum-verified download; a
  content-addressed, memory-mapped FM-index (with a correct pure-Python fallback
  when the Rust kernels are not built) for PAM-anchored candidate search; and
  cross-build liftover plus `flag_ambiguous_regions()`, which recommends
  T2T-CHM13 for segmentally-duplicated / centromeric / hg38-difficult loci and
  wires the recommendation into the Phase 1 result types.
- **Phase 3 — Data registry & population datasets.** `alleleforge.data`: a
  license-aware, versioned `DatasetRegistry` that never vendors a
  non-redistributable source and refuses to fetch an artifact it cannot
  checksum-verify; ClinVar parsing into normalized variants with
  significance/review-status and `get`/`by_rsid`/`by_gene`/`in_region` lookups;
  gnomAD per-population allele-frequency queries; 1000 Genomes and HGDP phased
  common-haplotype enumeration; dbSNP rsID ↔ locus resolution; and GENCODE gene
  models plus ENCODE bedGraph signal lookups. Every parser reads plain-text
  fixtures so CI needs no `pysam`/`cyvcf2`. Dataset versions, licenses, and
  citations are documented in `docs/data.md`.
- **Phase 4 — Variant resolver.** `alleleforge.variant`: `resolve(...)` turns a
  ClinVar accession, dbSNP rsID, HGVS (`g.`/`c.`/`p.`), VCF record, raw
  coordinates, or a raw target sequence into one canonical, **left-aligned**,
  reference-validated `Variant` (a ref/reference disagreement is a hard error)
  with its working interval and molecular consequence. Includes a
  dependency-free genomic-HGVS parser, an `HgvsAdapter` that projects coding /
  protein expressions through an injected backend, and a VEP-style
  `EffectPredictor` protocol with a deterministic static implementation.
- **Phase 5 — Off-target engine (population & haplotype aware).**
  `alleleforge.offtarget`: a five-stage [`search`][] — reference candidate
  search (PAM-anchored, ≤4 mismatches, ≤1 DNA + ≤1 RNA bulge, both strands;
  Rust FM-index with a correct linear-scan fallback), gnomAD **population
  augmentation** that finds *de novo* PAMs and strengthened seed-mismatch sites,
  **haplotype-aware** walking of common 1000G/HGDP haplotypes, an optional
  patient-VCF pass, then CFD+MIT scoring, thresholding (CFD ≥ 0.20 or MIT ≥ 0.10),
  de-duplication, and **ancestry stratification by default**. Published MIT/Hsu
  and CFD scorers (the exact Doench PAM table; an injectable mismatch table) plus
  a Cas12a CFD analog, behind a swappable `OffTargetScorer` protocol; an optional
  Cas-OFFinder cross-check. The reference-bias / `rs114518452` finding is
  reproduced as an integration test: a reference-only scan is blind to the
  ancestry-enriched off-target the population-aware scan nominates. Cites
  Hsu et al. *Nat Biotechnol* 2013, Doench et al. *Nat Biotechnol* 2016, and
  Cancellieri & Pinello *Nat Genet* 2023.

[`search`]: https://github.com/clay-good/alleleforge/blob/main/src/alleleforge/offtarget/engine.py
- **Phase 6 — Scoring foundations (model zoo, embeddings, uncertainty).** The
  reusable ML substrate before any chemistry-specific predictor.
  `alleleforge.model_zoo`: a `ModelRegistry` over required, validated YAML
  **model cards** that refuses a missing card, a license that forbids the use
  (non-commercial cards block commercial use; unknown/proprietary refused), or an
  unverifiable checkpoint, surfacing each as a Phase 1 `ModelCheckpoint`; bundled
  cards for Nucleotide Transformer v2 (500M) and Rule Set 3.
  `alleleforge.scoring`: a swappable `SequenceEmbedder` protocol (NT v2 default;
  Caduceus and Evo 2 adapters; a deterministic weight-free `StubEmbedder` and a
  hash-keyed embedding cache for CI); calibrated-uncertainty machinery — a
  deep ensemble (N=5, the default) whose interval widens on disagreement, an
  evidential (Normal-Inverse-Gamma) single-model fallback, quantile intervals,
  isotonic post-hoc calibration with `expected_calibration_error`, and an
  embedding-space `OODDetector`, all packaged into the Phase 1 `Prediction`; and
  the `Scorer` protocol with a runtime `ensure_prediction` guard enforcing the
  no-bare-float contract. Pure stdlib — no numpy/torch in the core path; real
  backbones are gated behind the `real_weights` marker. PyYAML joins the core
  dependencies for card parsing. Cites Hsu/Doench, Amini et al. *NeurIPS* 2020
  (deep evidential regression), and Dalla-Torre et al. *Nat Methods* 2024 (NT).
- **Phase 7 — Chemistry: SpCas9 nuclease.** The first full vertical slice
  (enumerate -> efficiency -> outcome -> off-target -> candidate).
  `alleleforge.enumerate.cas9`: strand-aware enumeration of every PAM-anchored
  guide whose blunt cut (3 bp 5' of the PAM) falls in the actionable window, with
  `NG`/SpRY fallback only when no `NGG` guide is actionable, an HDR donor for
  precise intents, and a guide-context helper. `alleleforge.scoring.cas9_efficiency`:
  a transparent Rule-Set-3-style baseline (with the DeWeirdt-Doench tracrRNA-aware
  term) and a backbone-fine-tuned deep-ensemble scorer with embedding-space OOD
  flagging — both calibrated `Prediction`s, never bare floats.
  `alleleforge.scoring.cas9_outcome`: a microhomology/MMEJ + templated-1-bp-insertion
  indel-spectrum baseline (the inDelphi mechanism) plus license-gated inDelphi /
  Lindel / X-CRISP adapters and an ensemble mode reporting inter-model top-allele
  agreement. `alleleforge.design.cas9`: `design_cas9` wires the slice into ranked
  `DesignCandidate`s, each with a calibrated efficiency interval, predicted outcome
  distribution, and ancestry-stratified off-target report. Bundled model cards for
  the efficiency ensemble and inDelphi. Cites DeWeirdt & Doench *Nat Commun* 2022
  (Rule Set 3) and Shen et al. *Nature* 2018 (inDelphi).
- **Phase 8 — Chemistry: base editing (ABE / CBE).** A declarative `BaseEditor`
  registry (deaminase, chemistry, window, PAM, motif preference) seeded with
  ABE8e, CBE4max, and evoCDA1 — adding an editor is a data change.
  `alleleforge.enumerate.base_editor.enumerate_base_edits` finds, for the
  transition a variant requires (only transition SNVs are base-editable;
  strand-aware), every sgRNA placing the target base in the activity window,
  annotated with target / bystander positions and the in-window composition.
  `alleleforge.scoring.base_outcome`: a transparent window-outcome baseline (the
  BE-DICT mechanism — per-position editing probability × motif preference,
  enumerating the 2^k window alleles) yielding the allele distribution plus
  calibrated `p_intended_exact` and `bystander_burden`, license-gated BE-DICT /
  BE-Hive adapters, and a cross-editor recommendation. `alleleforge.design.base_editor.design_base_editor`
  wires enumerate -> outcome -> off-target into `DesignCandidate`s ranked by exact-
  intended probability then bystander burden, flagging the cleanest as
  recommended and surfacing the tradeoff on every candidate. Phase 1
  `BaseEditWindow` gains optional placement/PAM and a `window_bases` property;
  `DesignCandidate` gains a `base_edit_window` reagent slot. Bundled BE-DICT
  model card. Cites Richter et al. 2020 (ABE8e), Koblan et al. 2018 (BE4max),
  Thuronyi et al. 2019 (evoCDA1), and Marquart et al. 2021 (BE-DICT).
- **Phase 9 — Chemistry: prime editing (the flagship).** The chemistry where no
  open-source tool combines all four axes — AlleleForge unifies them.
  `alleleforge.enumerate.prime.enumerate_prime`: full pegRNA enumeration (both
  strands via a reverse-complement frame) — for each PAM whose nick sits 5' of the
  edit, it enumerates **PBS 8-17 nt** and **RTT 7-34 nt** (covering the edit + >= 5
  nt 3' homology), attaches a **tevopreQ1** epegRNA motif by default, and selects a
  **PE3/PE3b** nicking guide (preferring a seed-disrupting PE3b ngRNA). Emits
  structurally-validated `PegRNA` + `NickingGuide` pairs.
  `alleleforge.scoring.prime_efficiency`: a transparent PRIDICT2.0-style baseline
  over the pegRNA geometry with an **ePRIDICT** chromatin adjustment (ENCODE
  tracks) and **prominent OOD honesty** — any context outside PRIDICT's HEK293T /
  K562 training distribution flags `in_distribution=False`; plus license-gated
  DeepPrime / GenET cross-check adapters. `alleleforge.scoring.prime_outcome`: an
  intended-vs-byproduct distribution (scaffold incorporation, partial RTT, indels)
  with calibrated intended probability. `alleleforge.design.prime.design_prime`
  wires enumerate -> efficiency -> outcome -> off-target into ranked
  `DesignCandidate`s, running the off-target engine on **both** nicks and merging
  them into one ancestry-stratified report. Phase 1 `PegRNA` gains optional
  placement / nick-site fields. Bundled PRIDICT2.0 card; canonical example
  `examples/01_clinvar_to_design.ipynb`. Cites Mathis et al. 2023/2024
  (PRIDICT / PRIDICT2.0 / ePRIDICT).
- **Phase 10 — Designer: routing, multi-chemistry menu, ranking.** The
  orchestrator that turns one variant into a ranked, explained menu across every
  eligible chemistry. `alleleforge.design.routing`: `eligible_chemistries` and
  `route` over a small table of transparent, inspectable `RoutingRule`s — each a
  chemistry paired with a one-line biological rationale and a pure
  `(resolved, intent)` predicate (a transition SNV → base editing; any precise
  small edit → prime; disruption intent → nuclease). Adding or relaxing a rule is
  a one-line data change and every verdict is explained.
  `alleleforge.design.ranking`: multi-objective ranking projecting every
  candidate — regardless of chemistry — onto four shared, higher-is-better
  objectives (calibrated efficiency, outcome cleanliness, off-target safety,
  reagent simplicity), ordered by a transparent weighted sum (defaults 0.35 /
  0.30 / 0.30 / 0.05, all overridable and echoed in output) **and** a Pareto
  front. The safety term is computed against the **worst-affected ancestry**, not
  the average, so a guide safe on average but dangerous in one population is
  correctly down-ranked. `alleleforge.design.designer.design`: resolves any input
  form (or an already-`ResolvedVariant`), routes, enumerates and scores per
  chemistry, ranks across them, and returns a `RankedMenu` with the Pareto front
  and a full provenance block. **Degrades gracefully** — an unavailable model, a
  failing enumeration, or a chemistry that finds nothing is recorded with its
  reason in the menu rationale while the rest of the menu still returns.
- **Phase 11 — Reporting & oligo output.** Turns a ranked menu into the
  artifacts users consume, leading with the research-use disclaimer and ending
  with full provenance on every render — **dependency-free**.
  `alleleforge.report.oligos`: cloning-ready annealed oligo duplexes per
  chemistry — SpCas9 / base-editor sgRNAs (vector overhangs + U6 `G`) and
  pegRNAs (spacer duplex + 3' extension carrying RTT + PBS + the epegRNA motif,
  plus the PE3/PE3b ngRNA duplex) — parameterized by named `VectorScheme`s
  (lentiGuide BsmBI, pX330 BbsI, pegRNA GG BsaI). Every set `reconstruct()`s the
  intended spacer / RTT / PBS, the headline round-trip invariant.
  `alleleforge.report.builder`: assembles a `RankedMenu` into a serializable
  `DesignReport` (per-candidate reagent summary, calibrated efficiency, top
  outcome alleles, ancestry-stratified off-target table, oligos, flags,
  rationale). `alleleforge.report.export`: JSON (full report, or the menu
  validated against the Phase 1 schemas), one-row-per-candidate TSV, and
  lazy-`polars` Parquet. `alleleforge.report.html`: a self-contained interactive
  HTML page — Plotly charts pulled from a CDN with figure specs inlined as JSON
  (no Python plotting dependency, no sequence data leaves the page) — and
  `alleleforge.report.pdf`: a small pure-Python writer emitting a valid,
  print-ready multi-page PDF. JSON Schemas emitted for the new report and oligo
  models. Cites the lentiCRISPRv2 (Sanjana et al. 2014), pX330 (Ran et al.
  2013), pegRNA GG-acceptor (Anzalone et al. 2019), and epegRNA motif (Nelson
  et al. 2022) cloning protocols.
- **Phase 12 — CLI (`aforge`).** A thin, reproducible, config-driven Typer shell
  over the library (new optional `cli` extra) with **no business logic** of its
  own. `aforge resolve` normalizes any input form; `aforge design` runs the full
  variant→ranked-menu pipeline and renders JSON / TSV / HTML / PDF (writing a
  `.provenance.json` sidecar next to file output); `aforge offtarget` runs a
  standalone population-aware search for a spacer; `aforge data list`/`show`
  inspects the dataset registry; `aforge bench` is wired for Phase 14. Global
  `--seed` / `--reference` / `--cache-dir` / `--verbose` / `--version`, a
  `--json` flag on every command, `--config run.toml` with CLI overrides, and
  ranking-`--weights` parsing. Meaningful, distinct exit codes (`0` ok, `2`
  usage, `3` missing data, `4` unavailable feature); runs are reproducible from
  the echoed seed + config modulo timestamp. The `aforge` entry point now
  resolves to the real Typer app; the CI test and type-check jobs install the
  `cli` extra. CLI usage page added to the docs.
- **Phase 13 — Web UI & API.** A FastAPI backend (`alleleforge.web.api`) exposing
  the library over HTTP and a dependency-free served single-page frontend
  (`alleleforge.web.frontend`). `create_app(...)` builds a thin async layer with
  **no business logic beyond orchestration**: `resolve`, `design`
  (`?format=json|html|pdf`), `offtarget`, `data` list/show, `bench`, and
  `health` endpoints, each validating requests/responses against the Phase 1 /
  Phase 11 pydantic schemas with auto-generated OpenAPI. Long design runs go
  through an **in-process async job queue** (`POST /api/jobs/design` →
  `GET /api/jobs/{id}`) that runs work in a worker thread with a state/progress
  status endpoint. The reference genome is supplied by the deployment
  (`create_app(reference=...)` or `ALLELEFORGE_REFERENCE_FASTA`); endpoints that
  need it return `503` until one is configured. The served frontend implements
  the variant-first journey (entry → ranked menu with interactive Plotly +
  ancestry-stratified off-target → oligo/report export) by embedding the
  server-rendered HTML report, with a prominent research-use disclaimer and a
  no-egress notice. **All compute is local: the app makes no outbound network
  call and transmits no sequence data externally**, asserted by a test that
  fails if any socket connects during a design request. New `Dockerfile` and
  `docker-compose.yml` for one-command local deploy; `httpx` added to the `web`
  extra and `pytest-asyncio` to `dev`; `GenomicInterval` gains a clean
  `chrom:start-end(strand)` `__str__`. 31 async endpoint tests (httpx +
  ASGITransport) cover every route, schema validation, the job lifecycle, exit
  paths, and the no-egress guarantee. Web API page added to the docs.
- **Phase 14 — CRISPR-Bench.** A standardized, calibration-first benchmark for
  guide- and edit-design models under `alleleforge.benchmark` (an installed
  subpackage, pure-Python and dependency-light, held to the same
  `mypy --strict`/ruff/coverage gates as the rest of the library). Five fixed
  task contracts (`tasks.py`): Cas9-efficiency and PE-efficiency (regression),
  Cas9-outcome and BE-outcome (distribution), and off-target-classification.
  Provenance-stamped, license-aware datasets (`datasets/`) shipped as small
  **synthetic fixtures** for CI, with the real corpora (Rule Set 3, FORECasT,
  BE-Hive, PRIDICT2, GUIDE-seq) fetched at runtime through the consent-gated
  registry. **Frozen, content-hashed splits** (`splits/`) with deliberate
  cross-cell-type test folds; `load_split()` re-verifies both the dataset content
  hash and the split membership hash on read and raises `SplitIntegrityError` on
  any drift — changing the data or the split requires a new version. A
  pure-Python metric battery (`metrics.py`): Spearman/Pearson, KL/top-k,
  AUROC/AUPRC, and **Expected Calibration Error required on every task**
  (interval coverage for regression, binned reliability for classification,
  predicted-mode reliability for distributions). A `runner.py` that evaluates any
  `BenchScorer` (the library's efficiency `Scorer`s already conform), enforces
  the no-bare-float contract at the seam, and emits a **signed** (content-hashed),
  provenance-stamped `BenchmarkResult`. A model-card-gated `leaderboard.py`
  (`Submission`/`Leaderboard`) that rejects unsigned, edited, or uncarded entries,
  ranks by metric direction (KL/ECE ascending), and renders static
  Markdown/HTML with calibration shown next to accuracy. A reference
  `BaselineScorer` fit on the train-fold marginal so every task runs out of the
  box. `aforge bench list` / `aforge bench run` wired over the runner. 63 tests
  (metrics vs hand-computed values, split-integrity tamper/drift detection,
  end-to-end runner across all kinds with signature reproducibility, leaderboard
  gating, and CLI). New `benchmark/README.md` (datasets/licenses/citations, split
  philosophy, submission format, launch plan), a CRISPR-Bench docs page,
  benchmark JSON schemas, and a deterministic fixture generator
  (`scripts/make_benchmark_fixtures.py`).
- **Phase 15 — Documentation, examples, and release.** Two new runnable example
  notebooks: `examples/02_population_offtarget.ipynb` (reproduces the
  reference-bias / `rs114518452` ancestry-stratified off-target finding;
  Cancellieri & Pinello, *Nat Genet* 2023) and `examples/03_batch_vcf.ipynb`
  (cohort-scale design reduced to one auditable summary with provenance). All
  three notebooks are **self-contained against the stub models** and **executed in
  CI** via a new `examples` job (`pytest --nbmake examples/ --no-cov`); `nbmake`
  and `ipykernel` added to the `dev` extra, and `01_clinvar_to_design.ipynb`
  normalized to nbformat 4.5 (cell ids). New docs pages: a deployment & operations
  guide (`docs/deployment.md`), an examples/tutorials gallery (`docs/examples.md`),
  and a methods-preprint outline (`docs/paper/outline.md`), all wired into the
  mkdocs nav and built strictly in CI. Release engineering: a tag-triggered
  `release.yml` workflow (build → PyPI via OIDC Trusted Publishing → multi-arch
  `linux/amd64`+`linux/arm64` Docker image to GHCR → GitHub Release), a Zenodo
  metadata file (`.zenodo.json`) for DOI minting on first tag, and a bioconda-style
  recipe (`conda/meta.yaml`). README updated with the runnable-examples gallery and
  the release/packaging matrix; all fifteen build phases are now complete.
- **v0.1.0 acceptance suite (`tests/test_acceptance.py`).** Encodes the
  specification's §16 "definition of done" as six executable end-to-end checks,
  complementing the per-component unit tests: a **ClinVar accession** flows
  through `design()` to a complete menu (every candidate carrying a calibrated
  efficiency interval, an outcome distribution, and an off-target report or an
  explicit reason); the unified entry point **reaches every chemistry** (base,
  prime, nuclease); a run is **reproducible from seed** (identical serialized
  menu); the **reference-bias / `rs114518452`** off-target case is reproduced;
  **prime editing unifies all four axes**; and **CRISPR-Bench publishes** the
  Cas9-efficiency, PE-efficiency, and off-target tasks with frozen splits,
  calibration, signed results, and a working leaderboard. All run against the stub
  models, so the release contract is verified on every CI run.
- **Native FM-index kernel (`aforge_native::bwt`).** The Rust crate now implements
  the genome-scale FM-index off-target search path the layout reserved for it:
  `fm_build` / `fm_count` / `fm_locate` and a `NativeFmIndex` object exposing
  `count`, `locate`, `pam_sites` (with IUPAC PAM expansion), `content_hash`, and
  `length`. `FMIndex.build(prefer_native=True)` transparently uses it when the
  crate is present and falls back to pure Python otherwise. Construction mirrors
  the Python fallback exactly (sentinel, C-table, checkpointed occ/rank, sampled
  suffix array, LF-walk, SHA-256 content hash), and a new parity test module
  (`tests/genome/test_native.py`, marked `native`) pins the native output to be
  **byte-identical** to the fallback across texts, patterns, and PAM sites. The
  CI `rust` job now builds the wheel and runs the parity suite; the existing
  FM-index tests are pinned to the pure-Python path so they stay deterministic
  whether or not the crate is built. Adds the `sha2` crate dependency.
- **Post-v0.1.0 roadmap (`SPEC_V2.md`).** A phase-structured contract for the work
  to "bake" the release before v1.0: R0 release hardening (pin real artifact
  hashes), R1 real-weights integration, R2 native `kmer`/`haplotype` kernels +
  SA-IS wired onto the off-target hot paths, R3 external-tool adapters, R4 scale,
  R5 validation/calibration + methods preprint, and the R6 v1.0 criteria.
- **R1 — consent-gated real backbone weights (first slice).** Real
  sequence-embedding backbones now resolve their weights through the
  license-gated, consent-required, checksum-verified model zoo instead of a bare
  `from_pretrained(model_id)`. Adds `ModelRegistry.authorize(name, *, use,
  consent)` (the license + consent gate for hub-resolved models, returning the
  provenance `ModelCheckpoint`); `SequenceEmbedder.resolve_weights()` (uses the
  pinned-artifact download+checksum path when the card pins a hash, else the
  authorize gate, recording the resolved checkpoint) and `model_checkpoint()`;
  and `EnsembleEfficiencyScorer.backbone_checkpoint()` so the cas9 efficiency
  chemistry stamps the backbone into provenance. Adds model cards for the
  `caduceus` and `evo2` backbones. The full consent/license/checksum flow is
  CI-tested with an injected downloader (no network, no torch — 8 new tests); the
  real tensor load stays behind the `real_weights` marker. The default backbone
  (Nucleotide Transformer v2, CC-BY-NC-SA) is loadable for research and refused
  for commercial use by the license gate.
- **R1 — consent-gated trained prime-efficiency adapters.** The trained
  prime-editing efficiency adapters (`DeepPrimeAdapter`, `GenETAdapter`) now
  resolve their weights through the same consent/license/checksum flow as the
  backbone: `resolve_weights()` (pinned-artifact download+checksum or the
  `authorize` gate) and `model_checkpoint()`, and `score()` runs the consent gate
  before any inference. Adds bundled, license-gated model cards for `deepprime`
  and `genet` (both research-only, so the license gate refuses commercial use).
  The flow is CI-tested with an injected downloader (no ML stack); the trained
  forward pass stays gated behind real weights. The `PridictScorer` heuristic
  baseline remains the CI default.
- **R1 — shared `WeightGate` + consent-gated outcome adapters.** Extracted the
  consent/license/checksum weight-resolution flow into a single
  `model_zoo.loader.WeightGate` mixin and refactored every trained model onto it
  (the sequence backbone, the prime-efficiency adapters, and now the cas9-outcome
  `InDelphi`/`Lindel`/`X-CRISP` and base-edit-outcome `BE-DICT`/`BE-Hive`
  adapters), removing four copies of the same logic. Each outcome adapter's
  `predict()` now runs the consent gate before inference. Adds bundled,
  license-gated cards for `lindel`, `x-crisp`, and `be-hive` (all research-only).
  The consent/license/checksum flow is CI-tested per chemistry with an injected
  downloader (no ML stack); the trained forward passes stay behind real weights.
  `loader.py` is at 100% coverage.
- **R2 — k-mer seed kernel on the off-target scan.** A native Rust k-mer kernel
  (`kmer.rs`: `kmer_seed_positions`) with a pure-Python fallback
  (`offtarget._kmer`) and a seed-and-extend prefilter wired into the off-target
  scan (`scan_sequence(..., seed=...)`). By the pigeonhole bound (partition the
  spacer into `E+1 = mismatches+dna_bulges+rna_bulges+1` blocks; ≥1 is uncut and
  substitution-free) any in-budget alignment shares an exact length-`k` seed with
  the spacer, so the prefilter is a **proven superset** — it never drops a hit.
  Equivalence is pinned by an exhaustive randomized test (400+ cases, seeded ≡
  brute-force across budgets/PAMs/strands), and the native seeding is pinned
  byte-for-byte to the Python path. The prefilter **auto-engages only when the
  seed is selective** (`k >= 5`); a micro-benchmark
  (`scripts/native_speedup.py`) measures **~2–4x** for high-stringency scans, a
  native seed lookup **~5–6x**, and a transparent no-op at the default
  ≤4-mismatch+bulge budget (where the FM-index is the genome-scale path). The CI
  rust job runs the native k-mer parity suite.
- **R2 — true-linear FM-index suffix array build (SA-IS).** The native FM-index
  suffix array (`bwt.rs`) is built by **SA-IS** (`sais.rs`, Nong–Zhang–Chan
  induced sorting, `O(n)`) — superseding the interim prefix-doubling
  (`O(n log² n)`) build, which itself superseded the direct sort's `O(n² log n)`
  that collapsed on the long poly-A / poly-N runs and tandem repeats real genomes
  contain. The unique sentinel keeps the suffix array unique, so it is
  byte-identical to the direct sort: pinned **directly** by a parity test of the
  newly-exposed `fm_suffix_array` against the ground-truth direct sort (textbook
  pathological inputs — all-same/alternating runs, tandem repeats — plus a 500-case
  fuzz) *and* end-to-end by the FM-index `count`/`locate`/`pam_sites` parity over
  low-complexity and random-long inputs. The CI rust job runs all of it.
- **R2 — FM-index seed-and-extend wired into the reference scan.** The
  off-target engine's stage-1 reference search now runs FM-index seed-and-extend
  (`scan_sequence(..., use_fm_index=...)`, threaded from `engine.search`): each
  concrete PAM is *located* in a content-addressed FM-index (the PAM is the seed)
  and only those anchors are *extended* by the shared alignment, replacing the
  linear `O(n)` PAM pass. It returns **byte-identical hits** to the brute-force
  scan — pinned by a randomized parity test at both the `scan_sequence` and
  `engine.search` levels (across mismatch/bulge budgets and both strands) — and
  **auto-engages per region** past `FM_INDEX_AUTO_THRESHOLD` (1 Mb), so
  genome-scale contigs take the indexed path while small inputs stay on the
  linear scan. The native Rust `bwt` kernel and the pure-Python FM-index share
  the interface; CI exercises the Python path, the rust job the native parity.
- **R2 — native haplotype-walk kernel wired into the haplotype engine.** A Rust
  kernel (`haplotype.rs`: `haplotype_apply_variants`) with a pure-Python fallback
  (`offtarget._haplotype`) materializes a common haplotype's alternative sequence
  by applying its full variant set to the reference window — applied right-to-left
  so indels keep later edits' coordinates valid, returning `None` on a
  reference-base clash (a phasing/coordinate mismatch the engine skips rather than
  mis-applying). It is wired into `offtarget.haplotype._apply_all` (the hot inner
  step of stage 3) and is **byte-identical** to the Python path, pinned by a fuzz
  parity test over lowercase refs, `N` bases, indels, overlaps, and
  out-of-window positions. The R2 micro-benchmark
  ([`scripts/native_speedup.py`](scripts/native_speedup.py)) measures **~4x**. With
  this the three spec kernels — `bwt`, `kmer`, `haplotype` — are all on their hot
  paths behind the fallback-plus-parity discipline; the CI rust job runs the
  native parity suite for each.
- **R3 — external tool adapters made real (Cas-OFFinder · VEP · HGVS).** The
  three previously-inert `NotImplementedError` adapters now have working
  implementations, each tested against **recorded fixtures** with the live
  network/binary call factored behind an injection point (opt-in,
  `live_integration`-marked, never run in CI):
  - **Cas-OFFinder** (`offtarget.cas_offinder_adapter`): `format_input` builds the
    binary's three-line input deck; `parse_output` reads both the legacy 6-column
    and bulge-aware 8-column result layouts into `(chrom, position, strand)` loci;
    `run(..., runner=...)` orchestrates write→invoke→parse with an injectable
    runner, and the existing `disagreements()` cross-check flags divergence from
    the native engine.
  - **VEP** (`variant.effect`): `VepRestPredictor` queries the Ensembl region
    endpoint through an injectable fetcher; `parse_vep_response` maps the JSON to a
    `VariantEffect` (MANE/canonical or named-transcript selection, most-severe SO
    term, impact tier), cached by `(variant, assembly, transcript)`.
  - **HGVS** (`variant.hgvs_adapter`): `HgvsLibraryProjector` wraps the real `hgvs`
    library (UTA + SeqRepo `AssemblyMapper.c_to_g`) behind the existing
    `HgvsProjector` interface, degrading to a clear `RuntimeError` when the
    optional library is absent.
  Adds the `live_integration` pytest marker for the opt-in live tests.
- **R4 — cohort-scale batch design (`design.design_many`).** Streams a whole
  cohort through `design`: the input is consumed lazily (a `cyvcf2` stream, a
  generator, or a list), and only the per-item working set is held — each ranked
  menu is summarized (and optionally written to `output_dir`), then released, so
  peak memory does not grow with cohort size (`on_result` makes the run `O(1)` in
  cohort size). Runs are **resumable** through a JSONL run manifest that opens
  with a provenance header (version, seed, reference build, intent, start time)
  and against which a re-run **skips items already recorded**; per-item failures
  are **captured, not fatal** (an unresolvable variant is recorded with its error
  and the cohort continues). A thread-parallel path (`max_workers` +
  `reference_factory`, since a pyfaidx handle is not thread-safe to share)
  produces summaries identical to the sequential run. Returns a `CohortRunReport`
  with the run counts and provenance.
- **R4 — `cyvcf2` fast path (`variant.iter_vcf`).** The streaming VCF adapter that
  *produces* the lazy iterator `design_many` consumes: it reads a VCF with
  `cyvcf2` (htslib-backed) and yields one `VcfRecord` per **concrete ALT allele**,
  splitting multi-allelic rows, skipping symbolic/`<DEL>`/spanning-`*`/non-ACGTN
  alleles, and dropping non-`PASS` records by default — so a whole-VCF cohort flows
  through the designer with bounded memory. The reader is **injectable**: a path is
  opened with `cyvcf2` lazily (a clear `RuntimeError` names the `genome` extra when
  it is absent), but any iterable duck-typed to the cyvcf2 `Variant` shape works,
  so the split/filter logic is fully CI-tested with a fake reader and **no native
  dependency**. (Whole-genome scale validation on a real VCF remains an opt-in
  nightly.)
- **R4 / Phase 12 — `aforge batch` cohort command.** The cohort path now reaches
  the CLI audience (the "three audiences, one core" principle): `aforge batch
  <input>` streams a whole cohort through `design_many`, **auto-detecting** a VCF
  (`.vcf`/`.vcf.gz`/`.bcf` → the `iter_vcf` cyvcf2 fast path) from a plain
  one-variant-per-line list (`#` comments skipped). It exposes the full streaming
  contract as flags — `--manifest` (resumable JSONL run), `--output-dir` (durable
  per-item menu JSON), `--max-workers` (thread-parallel with a per-worker
  reference), `--summary-tsv` (per-item table), plus `--intent`/`--populations`/
  `--weights`/`--no-offtarget` forwarded to `design`. Emits a human summary or, with
  `--json`, the full provenance-stamped run report; a VCF input without `cyvcf2`
  surfaces as a clean exit code `4` (unavailable), not a crash.
- **R4 / Phase 13 — `POST /api/batch` cohort endpoint.** Cohort design now reaches
  the **third audience** (the web): the endpoint takes a JSON variant list, runs
  `design_many`, and returns the per-item summaries, counts, and run provenance
  (per-item failures isolated, not fatal), all behind the same `503`-until-a
  -reference-is-configured contract as `/api/design`. The shared design knobs
  (intent/chemistries/weights) are factored into one `_design_options` helper used
  by both `/api/design` and `/api/batch`. Cohort design is now reachable from all
  three surfaces (library `design_many`, `aforge batch`, `POST /api/batch`) over one
  core.
- **R4 / Phase 13 — browser cohort UI.** The served single-page frontend gains a
  **cohort (batch) tab** beside the single-variant one: a one-variant-per-line
  textarea (blank/`#`-comment lines skipped) posts to `/api/batch` and renders the
  per-item summary table (status, best chemistry, efficiency, worst off-target,
  candidate count), with a JSON download. It keeps the no-egress, no-third-party
  -script guarantee — cohort design is now usable end to end from the browser.
- **Phase 13 fix — `GET /api/bench` lists the CRISPR-Bench tasks.** The endpoint
  previously returned a stale `501 "arrives in Phase 14"`; Phase 14 has shipped, so
  it now returns the five tasks with their kind, chemistry, dataset, primary metric,
  and metric battery (ECE included) — the HTTP mirror of `aforge bench list`.
- **Phase 14 — `aforge bench leaderboard` command.** `bench run` already emitted
  signed, provenance-stamped result JSONs but nothing aggregated them; the new
  command reads one or more result files, groups them by model into **card-gated
  submissions**, and renders the leaderboard as Markdown (default) or HTML. It
  enforces both honesty gates on read — every result must verify its own signature
  and carry a complete model card (name/license/citation) — so a number edited
  after signing, or a model without a card, is refused (exit `2`); a missing file
  exits `3`. The benchmark's "publish the leaderboard" story is now reachable from
  the CLI, not just the `Leaderboard` API.
- **R4 — content-addressed cross-run caches.** A shared
  `alleleforge.cache.ContentAddressedCache` — a sharded, atomically-written
  (temp-file-then-rename) disk key/value store under the cache dir, keyed by the
  SHA-256 of the inputs that determine a result — backs two cross-run memos:
  - **Embeddings:** `CachedEmbedder.persistent(embedder)` reuses embeddings across
    runs via a `PersistentEmbeddingCache` scoped per backbone identity (so two
    backbones never collide); a sequence embedded in one run is free in the next.
  - **Off-target:** `OffTargetCache` + `search(..., cache=...)` reuse the expensive
    reference scan. It is **safety-gated**: used only when the result is a pure
    function of the reference — the default scorer and no gnomAD/haplotype/patient
    augmentation — so a stale entry can never be served for a query whose external
    data the content key does not capture. A changed budget/PAM/threshold/reference
    is a distinct key; a custom scorer or any augmentation bypasses the cache.
- **R4 — whole-genome on-disk, memory-mapped FM-index (`genome.GenomeIndex`).**
  Builds one content-addressed FM-index per contig (both strands) over a
  reference, driven by **R2's native SA-IS**: the on-disk `FMIndex` build now uses
  the linear-time kernel (`_suffix_array` → `fm_suffix_array` when the crate is
  built), so the persistent + memory-mapped path scales to whole chromosomes
  instead of being limited to the pure-Python direct sort. The index **survives
  across runs** (a re-run memory-maps the cached contig index rather than
  rebuilding) and is queried over its memory map without pinning it in RAM. The
  off-target engine consumes it via `search(..., genome_index=...)` (and
  `scan_sequence(..., fm_plus=, fm_minus=)`) for the reference scan — **identical
  hits** to the per-call build (a parity test pins this across budgets and both
  strands), but built once and reused. Validated in CI on a downsampled-chromosome
  fixture in the rust job (native SA-IS build → mmap query → linear-scan parity →
  cross-run reuse); full hg38 / T2T-CHM13 builds are an opt-in nightly.
- **R5 — conformal interval recalibration + calibration-study script.**
  `scoring.ConformalCalibrator` recalibrates predictive *intervals* to a target
  coverage with the finite-sample **split-conformal guarantee** — the regression
  analog of `IsotonicCalibrator` for probabilities, and the first producer of the
  long-reserved `UncertaintyMethod.CONFORMAL`. It learns a single multiplicative
  width scale from a held-out calibration set, so recalibrated intervals meet the
  nominal coverage while the model's *relative* per-example uncertainty shape is
  preserved (normalized conformal). `empirical_coverage` measures interval coverage
  to decide when recalibration is needed. `scripts/calibration_study.py`
  regenerates the calibration report — every CRISPR-Bench task's primary metric and
  ECE, plus a conformal recalibration demonstration (coverage before/after at the
  spec's 80%/90% levels) — deterministically from config + seed. The recalibration
  machinery and the report are CI-tested on the weight-free splits; the real-data
  ECE numbers fill in with R1.
- **R5 — cross-cell-type generalization gap.** `benchmark.generalization_gap`
  quantifies the drop in a model's primary metric from an in-context fold (a
  training-seen cell type, default `val`) to the held-out cell type (default
  `test`) — the field-wide reality that a model tuned on one cellular context
  predicts an unseen one worse. The gap is **orientation-corrected** (positive
  always means worse held-out generalization, whether the metric is higher- or
  lower-is-better) via a `HIGHER_IS_BETTER` map, and computed through a shared
  `evaluate_fold` primitive. `scripts/calibration_study.py` now reports the
  per-task gap table (the cross-cell-type chemistry tasks; off-target, stratified
  by sequence pair, is excluded). Pinned by a test where a scorer that memorizes
  the in-context fold but is ignorant on the held-out one shows a positive gap.
- **R5 — methods-preprint draft.** `docs/paper/preprint.md` drafts the working
  outline into a full manuscript: abstract, methods (the domain model & provenance,
  the genome/variant front end, the population/haplotype off-target engine, the
  license-gated scoring substrate and uncertainty methods, the three chemistries,
  conformal recalibration, and the native kernels), the CRISPR-Bench design, the
  **weight-free end-to-end results** (the `rs114518452` reference-bias reproduction
  and the split-conformal coverage-before/after table regenerated from
  `scripts/calibration_study.py`), reproducibility, and discussion. The
  accuracy-vs-published-numbers results are explicitly fenced off as `[pending R1]`,
  so the draft never overstates what is measured. Wired into the docs nav (under a
  *Methods preprint* section) and linked from the outline, the README roadmap, and
  the citation block.
- **Docs — rendered diagrams on the published site + status fix.** Enabled
  Material's native **Mermaid** rendering (`pymdownx.superfences` custom fence) so
  the documentation site renders architecture and sequence diagrams as figures
  rather than code blocks, and gave the docs home (`docs/index.md`) the layered
  **architecture flowchart** and the **variant-first journey** sequence diagram that
  the README already carried. Fixed the stale build-status table on the docs home
  (Phase 14 CRISPR-Bench and Phase 15 docs/examples/release were still marked
  *next*/*planned* — both have shipped; all fifteen v0.1.0 phases now read *done*),
  and pointed the post-v0.1.0 roadmap at `SPEC_V2.md`.
- **R0 — supply-chain hardening.** Dependabot now tracks all three dependency
  surfaces — `pip`, `cargo`, and `github-actions` (`.github/dependabot.yml`,
  grouped weekly PRs); a CI `security` job runs `pip-audit` (PyPI advisory DB)
  and `cargo audit` (RustSec); and the release pipeline emits a **CycloneDX
  SBOM** over the resolved dependency closure (`sbom` job) and attaches it to the
  GitHub Release alongside the sdist/wheel.
- **R0 — reproducibility audit.** `scripts/reproduce.py` (and `make reproduce`)
  re-derives the canonical weight-free design run (a ClinVar accession → ranked
  menu, the §16.1 acceptance scenario) from config + seed, asserts run-to-run
  determinism, and diffs a canonicalized digest — volatile provenance stripped,
  floats rounded for cross-platform stability — against a committed golden
  manifest (`scripts/reproduce_golden.json`). A CI `reproduce` job gates it.
- **R0 — CI/CD runner hardening (Node 24).** Bumped every pinned GitHub Action off
  the deprecated Node 20 runtime, which GitHub force-migrates on 2026-06-16:
  `actions/checkout@v4→v5`, `actions/setup-python@v5→v6`, and (in the release
  pipeline) `actions/upload-artifact@v4→v7` + `actions/download-artifact@v4→v7` (the
  matched Node-24 pair, chosen over v8 to avoid its ESM/hash-mismatch breaking
  changes for the trivial named-artifact handoff), `softprops/action-gh-release@v2→v3`,
  and the Docker buildx stack (`setup-qemu@v3→v4`, `setup-buildx@v3→v4`,
  `login@v3→v4`, `metadata@v5→v6`, `build-push@v6→v7`). Both workflows now run
  entirely on Node 24; the CI workflow is verified green on the new majors, and the
  Docker/composite actions (`gh-action-pypi-publish`, `dtolnay/rust-toolchain`) are
  unaffected by the Node deprecation.

### Security

- **Bumped PyO3 `0.22.6` → `0.24.2`** in the `aforge_native` crate, resolving
  [GHSA / Dependabot #1](https://github.com/clay-good/alleleforge/security/dependabot/1)
  (risk of buffer overflow in `PyString::from_object`, fixed in PyO3 0.24.1). The
  crate's source already used the modern `Bound` API, so the upgrade was a clean
  dependency bump — verified with `cargo check`, `cargo clippy`, and a full
  `maturin develop` round-trip of `aforge_native.version()`.

### Changed

- **CI now gates the Rust crate.** A new `rust` job runs `cargo fmt --check`,
  `cargo clippy --lib -D warnings`, and `maturin build --release`, so the native
  toolchain (and its pinned, security-patched PyO3) is exercised on every push —
  closing the "Rust" leg of the v0.1.0 definition-of-done CI matrix and catching
  future dependency drift automatically.

[Unreleased]: https://github.com/clay-good/alleleforge/commits/main
