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

[Unreleased]: https://github.com/clay-good/alleleforge/commits/main
