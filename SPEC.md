# AlleleForge — Project Specification

> **A computational framework for CRISPR guide-RNA design and population-aware off-target analysis.**
> Input a sequence variant; receive a ranked, uncertainty-annotated set of candidate guide designs across
> SpCas9, base-editor, and prime-editor chemistries, each with a population- and haplotype-aware off-target
> profile. AlleleForge is an analysis and design tool that wraps existing published open-source software
> behind one typed interface.

> **Research and educational use only.** AlleleForge is computational. It produces ranked, explicitly
> uncertain *predictions* for research and method development. It contains no wet-lab protocols and no
> synthesis instructions. Off-target nominations are computational and must be experimentally validated.
> It is not a medical device and provides no medical advice.

---

## 0. How to read this document

This is the authoritative build specification for **AlleleForge**, written to be executed step by step by a
capable engineering agent. Each phase lists:

1. **Context** — why the phase exists and how it fits the whole.
2. **Deliverables** — the concrete files, modules, and tests that must exist when the phase is "done."
3. **Defaults & decisions** — every open choice is pre-filled with a default and an override path.

Build the phases **in order**. Phases 0–5 establish the spine (data model, genome access, off-target engine,
scoring interfaces) before any chemistry-specific or ML code. Do not begin Phase 6 (machine learning) until
Phases 1–5 have green CI.

Guiding principle: **wrap, don't rebuild.** Where excellent open-source tools exist (PRIDICT2.0, BE-Hive,
BE-DICT, inDelphi, CRISPRitz, Cas-OFFinder), AlleleForge integrates them behind a unified, typed interface
and adds value at the seams: a single variant-first UX, calibrated uncertainty, population-aware off-target
analysis for every chemistry, and a reproducible benchmark. New models are trained only where public
coverage is genuinely missing.

A phase is "done" only when its deliverables exist, `ruff` and `mypy --strict` pass on the new code, and its
tests are green in CI.

---

## 1. Project identity

| Field | Value |
|---|---|
| **Name** | AlleleForge |
| **Python package** | `alleleforge` |
| **CLI command** | `aforge` |
| **Tagline** | "Variant in, ranked design out." |
| **Repository** | `github.com/clay-good/alleleforge` |
| **License** | **MIT** (all code, schemas, benchmark, and any first-party model weights) |
| **Primary language** | Python ≥ 3.11 |
| **Performance extensions** | Rust via PyO3 / maturin |
| **Sister deliverable** | `crispr-bench` (CRISPR-Bench) — benchmark, splits, leaderboard |
| **Versioning** | SemVer 2.0; `0.x` until the three launch chemistries pass acceptance |
| **Code of conduct** | Contributor Covenant 2.1 |

The project is fully open source under a single permissive MIT license to maximize reuse, redistribution, and
academic adoption. Third-party tools and models that AlleleForge *wraps* retain their own upstream licenses;
the registry records each one and refuses to bundle any component whose license is incompatible with
redistribution, fetching it at runtime with the user's consent instead.

The CLI name `aforge` is short and, at time of writing, unclaimed on PyPI/conda — **verify availability as the
first action of Phase 1** and fall back to `alleleforge` as the command if `aforge` is taken.

---

## 2. Scope and non-goals

### 2.1 What AlleleForge does
Give any researcher — from a bench scientist with a ClinVar accession to an ML engineer building a pipeline —
a single, reproducible, well-typed path from **a sequence variant** to **a ranked, uncertainty-annotated set
of candidate guide designs**, with a population-aware off-target profile for each.

### 2.2 In scope (v1.0)
- **Input**: a variant as a ClinVar accession, dbSNP rsID, HGVS (genomic/coding/protein), VCF record, raw
  genomic coordinates, or a raw target sequence.
- **Three launch chemistries**:
  1. **SpCas9 nuclease** guide design (and HDR-template suggestion where applicable).
  2. **Base editing** (ABE and CBE families).
  3. **Prime editing** (pegRNA design: PBS, RTT, nicking guide, epegRNA motifs).
- **On-target efficiency** prediction with **calibrated uncertainty** for each chemistry.
- **Outcome prediction**: indel spectra (nuclease), bystander distribution (base editing), intended-vs-
  byproduct distribution (prime editing).
- **Off-target nomination** that is **reference-genome, population-aware, and haplotype-aware**
  (gnomAD / 1000G / HGDP), and optionally personalized from a supplied VCF — for *all three* chemistries.
- **Ranked candidate selection** across chemistries, recommending the most promising design for a variant.
- **Outputs**: machine-readable (JSON/TSV/Parquet), cloning-ready oligo sequences, and an HTML/PDF report.
- **Three interfaces**: importable Python library, `aforge` CLI, and a web UI.
- **CRISPR-Bench**: a versioned benchmark with frozen splits and a public leaderboard.

### 2.3 Out of scope (v1.0) — candidates for later minor versions
- Cas13 / RNA targeting — **v0.2**.
- CRISPRa / CRISPRi / epigenome editing — **v0.2**.
- Cas12a/Cpf1 as a first-class design chemistry — **v0.3** (off-target search supports its PAM from day one).
- Wet-lab automation, oligo-ordering vendor APIs, LIMS integration — explicitly deferred; v1.0 is
  computational only.
- Library-scale tiling-screen design — **v0.3**.
- Any clinical decision-making authority. AlleleForge is a research tool; it produces hypotheses and
  rankings, not medical advice. This is stated in the README, the docs, and every generated report.

### 2.4 Non-goals (permanent)
- AlleleForge will not be a closed SaaS, will not gate features behind payment, and will not transmit user
  sequences anywhere. All computation runs locally or on user-controlled infrastructure.
- AlleleForge will not silently substitute predictions for experimental validation. Every report states that
  off-target nomination is computational and must be experimentally confirmed.

---

## 3. Guiding design principles

1. **Variant-first.** The canonical user journey starts from a variant, not a guide. Chemistry selection,
   guide enumeration, and scoring are all downstream of "what is the variant and what design addresses it."
2. **Honest uncertainty.** Every numeric prediction ships with a calibrated interval. A confident wrong
   answer is worse than a wide honest one. No scorer returns a bare float.
3. **Population-aware by default.** Reference-genome-only off-target analysis is a known blind spot: a minor
   allele can create a *de novo* PAM that a reference-only scan misses. AlleleForge searches population
   variation by default and stratifies results by ancestry.
4. **Wrap, don't rebuild.** Integrate the best existing tools behind one typed interface; add new ML only at
   genuine coverage gaps.
5. **Reproducible to the byte.** Pinned environments, versioned datasets (DVC), deterministic seeds, and
   content-hashed model checkpoints. A result must be re-derivable from its provenance block.
6. **Three audiences, one core.** The library is the source of truth; CLI and web are thin shells. No
   business logic lives in the CLI or web layers.
7. **Typed and tested.** `mypy --strict`, `ruff`, and property-based tests on all core logic. Sequence
   biology is full of edge cases (strandedness, ambiguity codes, indels at boundaries); the type system and
   Hypothesis catch them.
8. **Cite everything.** Every dataset, model, and scoring function carries a literature citation and a
   version, in code and in output provenance.

---

## 4. High-level architecture

AlleleForge is layered. Lower layers know nothing about higher ones.

```
┌───────────────────────────────────────────────────────────────┐
│  Interfaces                                                     │
│  ┌────────────┐   ┌────────────┐   ┌───────────────────────┐   │
│  │  Python    │   │   aforge    │   │   Web UI (FastAPI +   │   │
│  │  library   │   │   CLI       │   │   React/Next.js)      │   │
│  └─────┬──────┘   └─────┬──────┘   └───────────┬───────────┘   │
│        └────────────────┴──────────────────────┘               │
├─────────────────────────┼───────────────────────────────────────┤
│  Orchestration                                                  │
│  ┌──────────────────────▼──────────────────────────────────┐   │
│  │  Designer: variant → chemistry routing → candidate menu  │   │
│  │  → scoring → outcome → off-target → ranking → report     │   │
│  └──────────────────────┬──────────────────────────────────┘   │
├─────────────────────────┼───────────────────────────────────────┤
│  Domain services                                                │
│  ┌───────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────┐  │
│  │ Variant   │ │ Guide        │ │ Scoring      │ │ Off-     │  │
│  │ resolver  │ │ enumerators  │ │ (efficiency, │ │ target   │  │
│  │ (HGVS,    │ │ (cas9, base, │ │ outcome,     │ │ engine   │  │
│  │ ClinVar)  │ │ prime)       │ │ uncertainty) │ │ (pop/hap)│  │
│  └─────┬─────┘ └──────┬───────┘ └──────┬───────┘ └────┬─────┘  │
│        └──────────────┴────────────────┴──────────────┘        │
├─────────────────────────┼───────────────────────────────────────┤
│  Foundations                                                    │
│  ┌───────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────┐  │
│  │ Genome    │ │ Data         │ │ Model        │ │ Core     │  │
│  │ access    │ │ registry     │ │ registry /   │ │ types &  │  │
│  │ (FASTA,   │ │ (DVC, gnomAD,│ │ zoo (ckpt    │ │ schemas  │  │
│  │ index)    │ │ ClinVar...)  │ │ hashing)     │ │          │  │
│  └───────────┘ └──────────────┘ └──────────────┘ └──────────┘  │
└───────────────────────────────────────────────────────────────┘
       Rust extensions (PyO3): FM-index off-target search, k-mer
       hashing, haplotype walking — called from the off-target
       engine and the enumerators.
```

The **Designer** is the only component that sees the full pipeline. Each **domain service** is independently
testable and usable. The **foundations** are pure infrastructure with no CRISPR-specific logic except the
core types.

---

## 5. Repository layout

```
alleleforge/
├── pyproject.toml                # build config, deps, tool config (ruff, mypy, pytest)
├── README.md
├── LICENSE                       # MIT
├── CITATION.cff
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── environment.yml               # conda environment (lockable via conda-lock)
├── dvc.yaml / .dvc/              # data versioning
├── Dockerfile                    # multi-stage, multi-arch (amd64 + arm64)
├── docker-compose.yml            # web UI + API
├── .github/workflows/            # CI: lint, type, test, build, docs, benchmark
├── docs/                         # mkdocs-material site
├── rust/                         # PyO3 crate: aforge_native
│   ├── Cargo.toml
│   └── src/
│       ├── lib.rs
│       ├── bwt.rs                # FM-index search
│       ├── kmer.rs               # k-mer hashing
│       └── haplotype.rs          # haplotype walking
├── src/alleleforge/
│   ├── __init__.py
│   ├── _version.py
│   ├── config.py                 # global config, defaults, paths
│   ├── types/                    # Phase 1: core domain types & schemas
│   │   ├── sequence.py           # Strand, DNASequence, GenomicInterval, ambiguity codes
│   │   ├── variant.py            # Variant, HGVS, VCF record models
│   │   ├── guide.py              # Spacer, PAM, Guide, PegRNA, BaseEditWindow
│   │   ├── edit.py               # EditOutcome, Chemistry, EditStrategy, EditIntent
│   │   ├── offtarget.py          # OffTargetSite, OffTargetReport
│   │   ├── prediction.py         # Prediction[T] with uncertainty
│   │   ├── candidate.py          # DesignCandidate, RankedMenu
│   │   └── provenance.py         # Provenance, ToolVersion, DatasetVersion
│   ├── genome/                   # Phase 2: reference access, FM-index, coordinates
│   ├── data/                     # Phase 3: registry, clinvar, gnomad, 1000G, hgdp, dbsnp, annotations
│   ├── variant/                  # Phase 4: resolver, hgvs adapter, effect (VEP)
│   ├── offtarget/                # Phase 5: engine, scoring, population, haplotype, cas-offinder adapter
│   ├── enumerate/                # Phases 7-9: cas9, base_editor, prime
│   ├── scoring/                  # Phases 6-9: base, uncertainty, backbone, per-chemistry scorers
│   ├── model_zoo/                # Phase 6: registry, cards/
│   ├── design/                   # Phase 10: designer, routing, ranking
│   ├── report/                   # Phase 11: builder, pdf, html, oligos
│   ├── cli/                      # Phase 12: Typer app
│   └── web/                      # Phase 13: api/ (FastAPI) + frontend/ (Next.js)
├── tests/                        # mirrors src/ ; pytest + hypothesis
├── benchmark/                    # CRISPR-Bench (own sub-package)
│   └── crispr_bench/             # datasets/, splits/, tasks.py, metrics.py, runner.py, leaderboard.py
└── examples/
    ├── 01_clinvar_to_design.ipynb   # the canonical journey
    ├── 02_population_offtarget.ipynb # reference-bias off-target validation case
    └── 03_batch_vcf.ipynb
```

---

## 6. Cross-cutting defaults (apply everywhere)

These hold across all phases unless a phase overrides them explicitly.

**Reference & coordinates.** Default reference **GRCh38/hg38**. T2T-CHM13 v2.0 is a first-class optional
reference, **auto-recommended** when a target lies in a segmentally duplicated, centromeric, or otherwise
hg38-ambiguous region (the genome layer flags these). mm39 ships for mouse; other Ensembl species download
lazily. All internal coordinates are **0-based, half-open** ("BED-style"); convert to 1-based only at I/O
boundaries that demand it (HGVS, VCF, human-readable reports), and label every coordinate with its system.

**Strand.** Always explicit (`Strand.PLUS` / `Strand.MINUS`); no "default strand." Spacers are stored 5'→3'
on their own strand with the genomic strand recorded.

**PAM defaults.** SpCas9 = `NGG` (primary), with `NAG` reported as a low-stringency off-target PAM. `NG`
(SpCas9-NG) and `NRN`/`NYN` (SpRY) are opt-in, auto-suggested only when no `NGG` exists within ±30 bp of the
target base. Cas12a = `TTTV` (off-target search support).

**Off-target search defaults.** Mismatches ≤ 4; DNA bulges ≤ 1; RNA bulges ≤ 1. Report any site with
**CFD ≥ 0.20** or **MIT ≥ 0.10**. Population search includes variants with **MAF ≥ 0.001** in any queried
population by default. De-novo PAM creation and seed-region mismatch changes from population variants are
always evaluated.

**Base-editing defaults.** Default editing window = protospacer positions **4–8** (1-based, PAM-distal end =
position 1), configurable per editor. Default editors: **ABE8e** (A•T→G•C) and **CBE4max/evoCDA1**
(C•G→T•A). Bystander editing is always predicted and reported.

**Prime-editing defaults.** Default architecture = **PE5max + epegRNA (tevopreQ1 3' motif)**; add a **PE3b
nicking guide** when a seed-disrupting ngRNA exists, else PE3. Default search ranges: **PBS 8–17 nt**,
**RTT 7–34 nt** (extended to cover the edit + ≥ 5 nt homology 3' of the edit). MMR context is a model input
where available.

**Uncertainty contract.** Every efficiency/outcome prediction returns a `Prediction[T]` carrying a point
estimate, a calibrated interval (default **80% predictive interval**), the method used, and an in-/out-of-
distribution flag. No scorer may return a bare float.

**Randomness.** Global seed default **20240501**, threaded through every stochastic step; recorded in
provenance.

**Provenance.** Every top-level result embeds a provenance block: AlleleForge version, all tool/model
versions and checkpoint hashes, all dataset versions, reference build, config snapshot, seed, and UTC
timestamp.

**Licensing of wrapped components.** Each wrapped tool/model records its upstream license in its card; the
registry refuses to bundle a component whose license is incompatible with redistribution and fetches it at
runtime with the user's consent.

---

# PART II — STEP-BY-STEP BUILD PHASES

Build in order. Each phase is self-contained.

---

## Phase 0 — Repository bootstrap & developer environment

**Context.** Before any sequence logic, establish a repository that is reproducible, typed, linted, and
CI-gated from commit one.

**Deliverables.**
- `pyproject.toml` using **hatchling**, declaring the `alleleforge` package and the `aforge` console script.
- Dependency groups: `core`, `genome`, `variant`, `ml`, `web`, `docs`, `dev`.
- `ruff` config (line length 100; rules E,F,I,UP,B,D; pydocstyle on public API), `mypy` config
  (`strict = true`), `pytest` config (coverage gate ≥ 85% on core).
- `environment.yml` for the scientific stack (pysam, pyfaidx, cyvcf2, mappy), lockable via conda-lock.
- Rust workspace `rust/` with a `maturin`-built PyO3 crate `aforge_native` exposing `version()` to prove the
  toolchain end to end. A test asserts the native version matches the Python package version.
- `.github/workflows/ci.yml`: matrix over Python 3.11/3.12 on Linux + macOS; jobs for lint, type-check,
  test, Rust build, and a docs build. Multi-arch Docker build on tags.
- `Dockerfile` (multi-stage), `docker-compose.yml` stub.
- `README.md` with the mission, the "research tool, not medical advice" disclaimer, and a quickstart.
- `LICENSE` (MIT), `CITATION.cff`, `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1), `CONTRIBUTING.md`,
  `CHANGELOG.md` (Keep a Changelog format).
- `src/alleleforge/_version.py` (single-source versioning); `config.py` defining default paths
  (XDG-compliant cache dir), the global seed (20240501), and a typed `Settings` (pydantic-settings)
  overridable by env vars and `~/.config/alleleforge/config.toml`; `__init__.py` re-exporting `__version__`
  and `Settings`.

**Defaults & decisions.** Build backend = hatchling. Config = pydantic-settings. CLI framework (declared now,
used in Phase 12) = **Typer**. Docs = mkdocs-material. Test = pytest + Hypothesis. Rust binding = PyO3 +
maturin. Cache root = `$XDG_CACHE_HOME/alleleforge` (fallback `~/.cache/alleleforge`). No CRISPR logic yet.
Ensure `ruff check`, `mypy --strict src`, `pytest`, and the Rust build all pass locally and in CI. Commit in
logical chunks with conventional-commit messages.

---

## Phase 1 — Core domain types & schemas

**Context.** The vocabulary the whole system speaks. Get strandedness, coordinate systems, ambiguity codes,
and the uncertainty contract right here, once.

**Deliverables.** Everything under `src/alleleforge/types/`:
- `sequence.py`: `Strand` enum; `CoordinateSystem` enum; `DNASequence` (validates ACGT + IUPAC ambiguity
  codes, knows its alphabet, ambiguity-aware reverse-complement, slicing that preserves coordinate metadata);
  `GenomicInterval` (chrom, start, end, strand, 0-based half-open, explicit coordinate system).
- `variant.py`: `Variant` (normalized: chrom, pos, ref, alt, build, optional HGVS strings and source IDs);
  `VariantClass` (SNV, MNV, insertion, deletion, indel, complex); typed wrappers for ClinVar accession and
  dbSNP rsID.
- `guide.py`: `PAM` (IUPAC pattern), `Spacer`, `Guide` (spacer + PAM + placement + cut site),
  `BaseEditWindow`, `PegRNA` (spacer, scaffold, RTT, PBS, optional 3' motif, optional nicking guide),
  `NickingGuide`.
- `edit.py`: `Chemistry` enum (CAS9_NUCLEASE, BASE_ABE, BASE_CBE, PRIME); `EditOutcome` (distribution over
  resulting alleles with probabilities); `EditStrategy` (binds a Variant to a Chemistry + reagent(s));
  `EditIntent` (correct, knock-out, install, revert).
- `offtarget.py`: `OffTargetSite` (locus, mismatches, bulges, score, score method, the population/haplotype
  context that produced it, ancestry annotation); `OffTargetReport` (aggregate + per-site list + summary
  stats + ancestry stratification).
- `prediction.py`: the **uncertainty contract** — generic `Prediction[T]` with `value: T`,
  `interval: tuple[float, float]`, `interval_level: float = 0.80`, `method: UncertaintyMethod`,
  `in_distribution: bool`, `calibrated: bool`, plus a helper to combine independent predictions.
- `candidate.py`: `DesignCandidate` (one chemistry + reagent(s) + efficiency `Prediction` + outcome
  `Prediction` + `OffTargetReport` + flags); `RankedMenu` (ordered candidates + ranking rationale +
  provenance).
- `provenance.py`: `ToolVersion`, `DatasetVersion`, `ModelCheckpoint` (content hash), `Provenance`.

**Defaults & decisions.** **pydantic v2** for everything serializable (validation + JSON Schema for free);
frozen dataclasses only for tight inner-loop value objects that never cross an I/O boundary. Coordinates
0-based half-open internally; add a `to_one_based()` boundary helper, never used internally. Reverse-
complement must be ambiguity-aware (R↔Y, W↔W, N↔N). All enums are `str`-valued for clean JSON. `Prediction`
default interval level = 0.80; forbid bare-float results by making scorers return `Prediction`. `PegRNA`
validates that RTT covers the edit plus required 3' homology and that PBS length is within range. Emit JSON
Schema for every public model into `docs/schemas/` via a small script wired into the docs build. Keep this
module free of I/O, genome access, and model code.

**Tests.** Exhaustive unit plus **Hypothesis property tests**: reverse-complement is an involution; ambiguity-
aware RC round-trips; coordinate conversions round-trip; `Variant` normalization is idempotent; `Prediction`
intervals always contain the point estimate and respect the level. Target ≥ 95% coverage on `types/`.

---

## Phase 2 — Genome access & indexing

**Context.** Nearly everything needs fast, correct access to reference sequence and a searchable index.

**Deliverables.** `src/alleleforge/genome/`:
- `reference.py`: `ReferenceGenome` wrapping `pyfaidx` for random access; a registry of built-in builds
  (hg38, T2T-CHM13 v2, mm39) and lazy, checksum-verified download of additional Ensembl species into the
  cache; `fetch(interval) -> DNASequence` that is strand-aware, bounds-checked, and N-pads contig ends while
  flagging the result. Never auto-download without the caller's consent flag.
- `index.py`: build/load an **FM-index** (delegating to the Rust `aforge_native` module) for PAM-anchored
  candidate search; content-addressed and cached on disk; **memory-mapped by default** with an opt-in
  `in_memory=True`. Document the expected on-disk size for hg38 and warn before building it.
- `coordinates.py`: liftover between builds (chain files) and `flag_ambiguous_regions()` that detects
  segmental-duplication / centromeric / hg38-difficult loci and recommends T2T-CHM13. Wire the recommendation
  into the Phase 1 result types.

**Defaults & decisions.** FASTA via pyfaidx. Index memory-mapped on disk by default. Downloads verified by
checksum and recorded as `DatasetVersion`. T2T auto-recommendation on by default. Contig-end policy: pad with
`N` and flag, never crash.

**Tests.** Strand-aware fetch against known loci using tiny bundled synthetic FASTAs (never full genomes in
CI); FM-index round-trip; liftover round-trips; ambiguous-region flagging on a curated fixture. Mock all
network downloads. Add a non-gating pytest-benchmark for index query latency.

---

## Phase 3 — Data registry & population datasets

**Context.** Population- and variant-aware analysis requires disciplined, versioned access to ClinVar,
gnomAD, 1000G, HGDP, dbSNP, GENCODE, and ENCODE tracks.

**Deliverables.** `src/alleleforge/data/`:
- `registry.py`: a `DatasetRegistry` on **DVC**; each dataset is a typed descriptor with `source_url`,
  `license`, `citation`, `version`, `sha256`, and `redistributable: bool`; access returns data plus a
  `DatasetVersion`. If not redistributable, never vendor it — fetch to the user's cache at runtime with
  explicit consent.
- `clinvar.py`: parse the monthly ClinVar release into normalized `Variant`s; `get(accession)`,
  `by_rsid(rsid)`, `by_gene(symbol)`, `in_region(interval)`; carry clinical significance and review status.
- `gnomad.py`: `frequencies(interval, populations=...)` against gnomAD v4.1, caching tabix slices.
- `thousand_genomes.py`, `hgdp.py`: phased haplotypes and per-population MAF; `common_haplotypes(interval,
  min_freq)` returning enumerable haplotype sequences for Phase 5.
- `dbsnp.py`: rsID↔locus via tabix (build 156+).
- `annotations.py`: GENCODE v47 gene models and ENCODE track access (DNase/ATAC/CTCF/H3K27ac) as per-locus
  signal lookups for later chromatin-aware scoring.

**Defaults & decisions.** DVC with a user-configured remote (default local cache; optional S3/GCS). gnomAD
default = **v4.1**. 1000G = phase 3 high-coverage. ClinVar = latest monthly snapshot, pinned per run. Default
population MAF threshold = **0.001**. ClinVar/gnomAD/1000G/HGDP/GENCODE are open; the registry blocks any
non-redistributable source from being vendored.

**Tests.** Parse tiny synthetic fixtures (never real multi-GB files in CI); verify normalization, frequency
lookups, haplotype enumeration, and that a non-redistributable dataset is never written into the repo or
image. Mock all network I/O. Document every dataset's version/license/citation in `docs/data.md`.

---

## Phase 4 — Variant resolver

**Context.** The front door of the variant-first journey. Any accepted input must normalize to a single
canonical `Variant` with its genomic placement, coding/protein consequence, and working window.

**Deliverables.** `src/alleleforge/variant/`:
- `resolver.py`: `resolve(input, *, build="hg38", window=100, transcript="MANE_SELECT") -> ResolvedVariant`
  accepting ClinVar accession, dbSNP rsID, HGVS (g./c./p.), VCF record, raw coordinates, or a raw sequence
  with a marked target position. Left-aligns and trims indels, validates the asserted ref against the
  reference (hard error on mismatch — likely wrong build), and returns the canonical `Variant` plus a working
  `GenomicInterval` (default ±100 bp, configurable).
- `hgvs_adapter.py`: wrap the `hgvs` library for parsing/validation and projection between c./g./p. using
  MANE Select (fallback RefSeq canonical). Handle intronic offsets, UTR coordinates, and protein-level inputs
  that map to multiple codons (return all, flagged).
- `effect.py`: VEP integration (REST default, local optional) returning a structured consequence
  (missense/nonsense/splice/frameshift/…) used by the Phase 10 router. Cache responses by variant +
  transcript set.

**Defaults & decisions.** Transcript default = **MANE Select**. Indels **left-aligned and parsimonious**
(bcftools-norm semantics). Default window ±100 bp. VEP via REST by default.

**Tests.** Round-trip a curated set of variants (SNV, splice, small indel) from each input form to the same
canonical `Variant`; left-alignment on tricky repeat-region indels; reference-mismatch detection; mock VEP
and hgvs network calls. Property test: resolution is idempotent and input-form-invariant.

---

## Phase 5 — Off-target engine (reference, population, haplotype-aware)

**Context.** AlleleForge's safety core and a primary point of novelty: population- and haplotype-aware
off-target nomination for **every** chemistry. Build it before the chemistries so each plugs into one engine.

**Deliverables.** `src/alleleforge/offtarget/`:
- `engine.py`: `search(spacer, pam, *, reference, mismatches=4, dna_bulges=1, rna_bulges=1, populations=ALL,
  maf=0.001, patient_vcf=None) -> OffTargetReport`. Five stages: (1) reference candidate search via the Rust
  FM-index; (2) **population augmentation** — inject gnomAD/1000G/HGDP variants to find *de novo* PAMs and
  altered-mismatch sites; (3) **haplotype-aware** evaluation walking common haplotypes (Rust `haplotype.rs`);
  (4) optional **patient VCF** pass; (5) scoring and aggregation. Returns an `OffTargetReport` that is
  **ancestry-stratified by default**. Every threshold is a parameter.
- `scoring.py`: CFD (with the published Doench mismatch/PAM weight tables, cited in code), the MIT
  specificity score, and a Cas12a CFD analog; a `Scorer` protocol so Phase 6 ML scorers can be swapped in.
- `population.py`: takes a window's variants and enumerates the off-target sites they create or modify, each
  annotated with the causal allele, the populations carrying it, and the frequency. **Reproduce the published
  reference-bias validation case** (BCL11A enhancer / `rs114518452`): a minor allele creating a de-novo NGG
  PAM that yields a high-CFD off-target, reported with ancestry-stratified frequency. Ship as an integration
  test, citing Cancellieri & Pinello, *Nat Genet* 2023.
- `haplotype.py`: Python orchestration over the Rust haplotype walker.
- `cas_offinder_adapter.py`: optional cross-check against Cas-OFFinder when installed; flag disagreements.

**Defaults & decisions.** Defaults as in §6 (≤4 mismatch, ≤1 DNA + ≤1 RNA bulge, CFD≥0.20 or MIT≥0.10,
MAF≥0.001, all populations). Native Rust engine is primary; Cas-OFFinder is the cross-check. Every site
records whether it exists in the reference, arises from a population variant (which allele, which
populations, frequency), or arises from the patient's VCF. Reports are **ancestry-stratified by default**.

**Tests.** Exact and tolerant search correctness on synthetic genomes; CFD/MIT against published worked
examples; population augmentation finds de-novo PAMs in fixtures; haplotype walking enumerates expected
haplotypes; patient-VCF personalization; the reference-bias integration test passes. Non-gating genome-wide
search benchmark on a synthetic reference.

---

## Phase 6 — Scoring foundations: model zoo, backbone embeddings, uncertainty

**Context.** The reusable ML substrate before any chemistry-specific predictor.

**Deliverables.**
- `model_zoo/registry.py`: register, download, verify (content hash), and load checkpoints; each has a
  required **model card** (`cards/*.yaml`: name, version, chemistry, training_data, metrics, intended_use,
  out_of_scope_use, license, citation, known_failure_modes, checkpoint_sha256). Loading fails loudly if the
  card is missing or the license forbids the use. Surface every checkpoint as a `ModelCheckpoint`.
- `scoring/backbone.py`: a `SequenceEmbedder` protocol with `embed(sequences) -> Tensor`, `context_window`,
  `name`, `version`. Default adapter = **Nucleotide Transformer v2 (500M)**; Caduceus and Evo 2 adapters
  behind the same protocol (interface mandatory, full impl optional). Cache embeddings by sequence hash.
- `scoring/uncertainty.py`: `DeepEnsemble` (N=5 default), an evidential-regression head, quantile heads, and
  isotonic post-hoc calibration with `expected_calibration_error(...)`; `to_prediction(...)` packaging
  outputs into the Phase 1 `Prediction` (80% interval, method tag, `calibrated` flag, and an
  `in_distribution` flag from embedding-space density vs. a stored training reference).
- `scoring/base.py`: the `Scorer` protocol returning `Prediction` and exposing its model card; a guard
  (test + runtime assert) that no `Scorer` returns a bare float.

**Defaults & decisions.** Default backbone = NT v2 500M. Uncertainty default = deep ensemble (N=5) with
isotonic calibration; evidential is the single-model fallback. Default interval = 80%. OOD via embedding-space
density. Inference supports `torch.compile` and optional ONNX export.

**Tests.** Registry rejects missing/forbidden-license cards and corrupted checkpoints; embedder produces
stable cached embeddings on a tiny **stub** model (no real 500M weights in CI); ensemble intervals contain
the mean and widen on held-out OOD inputs; calibration reduces ECE on a synthetic miscalibrated fixture; OOD
flag fires on far-from-training embeddings. Gate real-weight tests behind an opt-in marker.

---

## Phase 7 — Chemistry: SpCas9 nuclease (enumeration, efficiency, outcome)

**Context.** The most mature chemistry and the right one to prove the full vertical slice (enumerate → score
→ outcome → off-target → candidate).

**Deliverables.**
- `enumerate/cas9.py`: `enumerate_cas9(resolved, intent, *, pam="NGG", allow_ng=False, allow_spry=False) ->
  list[Guide]`. Enumerate all PAM-anchored spacers whose cut site (default 3 bp 5' of PAM) can achieve the
  intent within the actionable window; place each strand-aware. Propose an HDR donor template for precise
  correction intent. Emit NG/SpRY guides only when no NGG guide is actionable and the flag is set.
- `scoring/cas9_efficiency.py`: an on-target efficiency `Scorer` with (a) a **Rule Set 3** adapter as a
  no-large-download baseline and (b) a backbone-fine-tuned deep-ensemble model from the model zoo. Both
  return calibrated `Prediction`s. Include the tracrRNA-aware feature from DeWeirdt-Doench (*Nat Commun*
  2022); cite it.
- `scoring/cas9_outcome.py`: adapters to **inDelphi, Lindel, X-CRISP**, each returning an `EditOutcome`
  distribution over indel alleles; an ensemble mode that reports inter-model agreement as an uncertainty
  signal. License-gate via the model zoo.

**Defaults & decisions.** Primary PAM NGG; suggest NG/SpRY only when no NGG places a cut in the actionable
window. Default efficiency = backbone-fine-tuned ensemble; Rule Set 3 always-available baseline. Default
outcome = inDelphi, with Lindel and X-CRISP available and an ensemble/agreement option. Cut site default =
3 bp 5' of PAM. All scores carry 80% intervals and an OOD flag.

**Integration + tests.** Wire enumeration → efficiency → outcome → Phase 5 off-target into a `cas9` path that
yields `DesignCandidate`s. End-to-end test on a curated ClinVar variant producing a ranked set with
intervals, outcomes, and ancestry-stratified off-target. Enumeration completeness/strandedness; efficiency
baseline matches Rule Set 3 within tolerance; outcome adapters reproduce published example distributions; OOD
fires on non-human input. CI weight-free with stubs.

---

## Phase 8 — Chemistry: base editing (ABE / CBE)

**Context.** The hard part is predicting the **window outcome**: which target base(s) get edited and what
bystanders ride along. Mature predictors (BE-Hive, BE-DICT) exist and should be wrapped.

**Deliverables.**
- A declarative `BaseEditor` registry (deaminase, edit chemistry, default window, PAM, motif preferences)
  seeded with ABE8e, CBE4max, evoCDA1; adding an editor is a data change, not code.
- `enumerate/base_editor.py`: `enumerate_base_edits(resolved, *, editors=DEFAULTS, window=(4,8)) ->
  list[BaseEditWindow]`. For the required chemistry, find spacers placing the target base in-window per
  editor; annotate clean vs. bystander-present and the in-window base composition.
- `scoring/base_outcome.py`: wrap **BE-DICT** (default) and **BE-Hive** (optional) behind one interface
  returning an `EditOutcome` over alleles; compute `p_intended_exact` and `bystander_burden`, each a
  calibrated `Prediction`; a cross-editor recommendation maximizing clean-edit probability. License-gate via
  the model zoo.

**Defaults & decisions.** Window 4–8 (configurable per editor). Default editors ABE8e (A→G) and
CBE4max/evoCDA1 (C→T). Outcome default = BE-DICT, BE-Hive optional, ensemble/agreement option. The designer
prefers the editor/guide combination maximizing P(exact intended allele) while minimizing bystander burden,
and surfaces the tradeoff explicitly.

**Integration + tests.** Enumeration → outcome → Phase 5 off-target → `DesignCandidate`s. End-to-end test on
a splice-donor or missense variant correctable by ABE, asserting a ranked set with explicit bystander
tradeoffs and ancestry-stratified off-target. Window placement correctness across editors; bystander
detection; outcome adapters reproduce published distributions; recommendation prefers higher clean-edit
probability. CI weight-free with stubs.

---

## Phase 9 — Chemistry: prime editing (the flagship gap)

**Context.** The chemistry where AlleleForge contributes the most: no open-source tool today combines
variant input + ML efficiency + chromatin context + population-aware off-target + outcome/byproduct
prediction. PRIDICT2.0 is SOTA for efficiency but has no variant front-end and no off-target module;
PrimeDesign/PrimeVar give ClinVar→pegRNA but only rule-based scoring and reference-only off-target; CRISPRme
does population off-target but designs no pegRNAs. AlleleForge stitches these together and fills the seams.

**Deliverables.**
- `enumerate/prime.py`: full pegRNA enumeration: choose nick site and spacer; enumerate **PBS (8–17 nt)** and
  **RTT (7–34 nt, covering edit + ≥5 nt 3' homology)**; select a **PE3/PE3b nicking guide** (prefer a
  seed-disrupting PE3b ngRNA); attach the **tevopreQ1 epegRNA 3' motif** by default; respect MMR context.
  Emit validated `PegRNA` + `NickingGuide` pairs (Phase 1 structural checks).
- `scoring/prime_efficiency.py`: wrap **PRIDICT2.0** as the default efficiency `Scorer`; integrate
  **ePRIDICT** for chromatin-context adjustment using Phase 3 ENCODE tracks when a cell context is supplied;
  add a DeepPrime/GenET cross-check adapter. Return calibrated `Prediction`s and set `in_distribution=False`
  whenever the target/cell context is unlike PRIDICT's HEK293T/K562 training distribution — surface this
  prominently. License-gate all wrapped models.
- `scoring/prime_outcome.py`: predict intended-vs-byproduct distribution (scaffold incorporation, partial
  RTT, indels) as an `EditOutcome` with uncertainty.
- Off-target: run the Phase 5 engine on **both** the pegRNA-induced nick and the ngRNA nick; merge into one
  ancestry-stratified `OffTargetReport`.

**Defaults & decisions.** Default architecture PE5max + epegRNA(tevopreQ1) + PE3b-when-possible. PBS 8–17 nt,
RTT 7–34 nt — search both and let the efficiency model rank. Efficiency default = PRIDICT2.0; apply ePRIDICT
when a cell context is given; **always** show the OOD flag. Off-target run for both nicks by default.

**Integration + tests.** Implement `examples/01_clinvar_to_design.ipynb` showing a variant flowing to a
ranked pegRNA design with calibrated efficiency, predicted byproducts, and an ancestry-stratified off-target
report. End-to-end test asserting a structurally valid top pegRNA with all four axes populated. PBS/RTT
boundaries; PE3b preference logic; motif attachment; efficiency adapter reproduces PRIDICT2 example values
within tolerance; OOD fires on non-HEK/K562 contexts; both nicks searched. CI weight-free with stubs.

---

## Phase 10 — Designer: routing, multi-chemistry candidate menu, ranking

**Context.** The orchestrator that realizes the variant-first promise: from one variant, decide which
chemistries are eligible, generate candidates from each, score them on one footing, and return a ranked,
explained menu.

**Deliverables.** `src/alleleforge/design/`:
- `routing.py`: `eligible_chemistries(resolved, intent) -> list[Chemistry]` as transparent, inspectable
  rules driven by variant class + VEP consequence + intent (e.g., a single-transition SNV correctable
  in-window → base editing eligible; any precise small edit → prime eligible; disruption intent → nuclease
  eligible). Document each rule's biological rationale; make adding a rule trivial.
- `designer.py`: `design(input, *, intent, populations, patient_vcf=None, ...) -> RankedMenu`. Resolves the
  variant (Phase 4), routes, enumerates and scores candidates per eligible chemistry (Phases 7–9), runs
  off-target (Phase 5), assembles `DesignCandidate`s, ranks them, and attaches full provenance. Runs any
  subset of eligible chemistries and degrades gracefully if one chemistry's model is unavailable (reports
  why, continues).
- `ranking.py`: multi-objective ranking over (calibrated efficiency, outcome cleanliness, off-target safety
  with ancestry-aware penalty, simplicity). Default = a transparent weighted sum **and** a Pareto-front view.
  Compute the safety term against the **worst-affected ancestry**, not the average. Human-readable rationale
  per candidate, stored in the menu.

**Defaults & decisions.** Default intent inferred from variant + a user hint (`correct` by default). Default
weights: efficiency 0.35, outcome cleanliness 0.30, off-target safety 0.30, simplicity 0.05 — all
overridable and shown in output. Ranking always exposes the Pareto front. Safety penalty uses the
worst-affected ancestry so a design that is safe on average but dangerous in one population is correctly
down-ranked.

**Tests.** Routing yields the correct eligible set on curated SNV/indel/splice fixtures; `design(...)`
returns a populated `RankedMenu` with provenance on an end-to-end case; ranking is stable, weight-sensitive
in the expected direction, and the ancestry-worst-case penalty down-ranks a reference-biased guide relative
to a population-safe alternative. Property test: every candidate has efficiency, outcome, and off-target
populated or an explicit reason it does not.

---

## Phase 11 — Reporting & oligo output

**Context.** Bench scientists need cloning-ready sequences and a shareable report; pipelines need clean
machine-readable output. Every report carries the research-use disclaimer and full provenance.

**Deliverables.** `src/alleleforge/report/`:
- `oligos.py`: emit cloning-ready oligos per candidate — Cas9 sgRNA oligos with vector-appropriate overhangs;
  base-editor sgRNA oligos; pegRNA + ngRNA oligos for standard pegRNA cloning (scaffold + tevopreQ1 motif).
  Parameterize by vector/overhang scheme with named defaults. Validate that round-tripping the oligos
  reconstructs the intended spacer/RTT/PBS.
- `builder.py`: assemble a `RankedMenu` into a structured, serializable report model (candidates, scores with
  intervals, outcome distributions, ancestry-stratified off-target tables, provenance, disclaimer).
- `html.py` / `pdf.py`: render the report. HTML embeds interactive Plotly off-target/outcome plots and an
  optional JBrowse 2 context view; PDF is static and print-ready. Both lead with the disclaimer and end with
  provenance.
- Machine-readable export: JSON (validated against the Phase 1 schemas), TSV, and Parquet.

**Defaults & decisions.** Default machine output = JSON + TSV; Parquet for batch. Default human output = HTML
with a PDF option. Oligo output defaults to common vector schemes, naming the scheme explicitly.

**Tests.** Oligo round-trip correctness per chemistry and vector scheme; the report includes disclaimer +
provenance on every render; JSON validates against schema; HTML and PDF render without error on an end-to-end
menu fixture; off-target tables are ancestry-stratified.

---

## Phase 12 — CLI (`aforge`)

**Context.** A thin, reproducible, config-driven CLI over the library. No business logic here.

**Deliverables.** `src/alleleforge/cli/main.py` (Typer):
- `aforge design` — variant → ranked menu; accepts every input form; flags for intent, chemistries,
  populations, patient VCF, reference build, output formats, ranking weights; `--config run.toml` with CLI
  overrides; the resolved config is echoed into provenance.
- `aforge offtarget` — standalone population/haplotype-aware off-target for a supplied spacer.
- `aforge resolve` — show the normalized variant + consequence for any input (debugging aid).
- `aforge data` — manage datasets (status, fetch, refresh, show versions/licenses).
- `aforge bench` — run CRISPR-Bench tasks (Phase 14).
- Global: `--seed`, `--reference`, `--cache-dir`, `--verbose`, and machine-readable `--json` everywhere.

**Defaults & decisions.** Typer for ergonomics + auto-help. Every command can emit JSON. Runs are
reproducible from the echoed config + seed. Long operations show progress and write a provenance sidecar next
to outputs. Meaningful, distinct exit codes for input errors, missing data, and unavailable models.

**Tests.** Invoke each subcommand via Typer's test runner on fixtures; reproducibility (same config + seed →
identical output modulo timestamp); JSON mode is schema-valid; exit codes. Generate a CLI usage page from the
Typer app.

---

## Phase 13 — Web UI & API

**Context.** The accessible front door for users who will not touch a terminal. A FastAPI backend exposes the
library; a Next.js frontend provides the variant-first journey visually. Sequences never leave the user's
deployment.

**Deliverables.**
- `src/alleleforge/web/api/`: a FastAPI app exposing `resolve`, `design`, `offtarget`, `data`, and `bench`
  as async endpoints; long runs go through a task queue with progress and a job-status endpoint; OpenAPI
  auto-generated; the Phase 1 schemas validate request/response. No business logic beyond orchestration.
- `src/alleleforge/web/frontend/`: a Next.js + React app implementing the journey — variant entry (all input
  forms) → eligible chemistries → ranked candidate menu with interactive Plotly efficiency intervals and
  outcome distributions → an **ancestry-stratified off-target browser** with embedded JBrowse 2 → oligo/report
  export. Prominent research-use disclaimer; state that no sequence data is transmitted externally.
- `docker-compose.yml`: one-command local deploy of api + frontend + worker, wired to a local cache volume.

**Defaults & decisions.** Backend FastAPI; frontend Next.js (Streamlit acceptable for a v0 internal preview).
Plotly for charts, JBrowse 2 for genome context. All compute local/user-controlled; **no telemetry, no
external sequence transmission**. Async job model with progress. Auth is deployment-optional (default local
deploy is single-user, no auth).

**Tests.** API endpoint tests (httpx/async) including schema validation and the async job lifecycle; a
minimal frontend e2e (Playwright) covering variant entry → candidate menu; verify no outbound call carries
sequence data (assert against a mock egress). Heavy models stubbed in CI.

---

## Phase 14 — CRISPR-Bench: benchmark, splits, model zoo, leaderboard

**Context.** The sister deliverable and a field-level contribution: versioned datasets, frozen splits,
standard metrics, and a public leaderboard — a common yardstick for guide design. Independently valuable and
publishable even before AlleleForge is feature-complete.

**Deliverables.** `benchmark/crispr_bench/`:
- `datasets/`: license-aware, provenance-stamped ingestion of the major public datasets — Rule Set 3
  validation, DeepHF/DeepSpCas9 (Cas9 efficiency); FORECasT, inDelphi, Lindel (nuclease outcomes); BE-Hive,
  BE-DICT (base-edit outcomes); PRIDICT2 Library-Diverse (pegRNA efficiency); CRISPRsql / GUIDE-seq
  aggregates (off-target). Each with provenance, license, and citation; non-redistributable parts fetched at
  runtime via the Phase 3 registry.
- `splits/`: **frozen, content-hashed** train/val/test splits, including deliberate **cross-cell-type and
  cross-context** test splits to measure generalization. A loader verifies the hash on read; changing data
  requires a new split version.
- `tasks.py`: the five tasks (Cas9-efficiency, Cas9-outcome, BE-outcome, PE-efficiency,
  off-target-classification) with fixed input/label contracts.
- `metrics.py`: Spearman/Pearson (efficiency), KL/top-k (outcomes), AUROC/AUPRC (off-target), **plus
  calibration (ECE) as a first-class required metric** on every task.
- `runner.py`: evaluate any object implementing the `Scorer` protocol against a (task, split) pair and emit a
  signed, provenance-stamped result JSON. Wire `aforge bench` to it.
- `leaderboard.py`: a submission format requiring a model card; a static leaderboard site (HuggingFace
  Spaces / Polaris compatible) displaying metrics, calibration, and split version per entry.

**Defaults & decisions.** Splits immutable once published and content-hashed; a new split is a new version.
ECE required on every task. The leaderboard accepts external submissions with model cards. Hosting target:
HuggingFace + Polaris. `benchmark/README.md` documents datasets/licenses/citations, the split philosophy, how
to submit, and the lab-outreach launch plan.

**Tests.** Split hashes stable and verified on load; metrics match hand-computed values on tiny fixtures; the
runner scores a stub model end to end; a sample submission renders on the leaderboard. All datasets in CI are
small synthetic fixtures.

---

## Phase 15 — Documentation, examples, and release

**Context.** A tool only contributes if people can use, trust, and cite it.

**Deliverables.**
- `docs/` (mkdocs-material): concept guide (variant-first philosophy, the uncertainty contract,
  population-aware safety and why ancestry stratification matters), tutorials, full API reference
  (mkdocstrings), the data-provenance page, the CLI reference (from the Typer app), a deployment guide, and a
  prominent ethics/scope page (research-use-only; not medical advice; off-target requires validation;
  responsible/dual-use note).
- `examples/`: `01_clinvar_to_design.ipynb` (the canonical journey across all three chemistries),
  `02_population_offtarget.ipynb` (reproduce the reference-bias / `rs114518452` ancestry-stratified
  off-target finding from a documented fixture; cite Cancellieri & Pinello, *Nat Genet* 2023),
  `03_batch_vcf.ipynb` (cohort-scale design).
- Release: PyPI + bioconda + multi-arch Docker images + a tagged GitHub release with a Zenodo DOI;
  `CITATION.cff` finalized; a short methods-preprint outline in `docs/paper/`.

**Defaults & decisions.** Docs = mkdocs-material + mkdocstrings, built in CI, deployed on tag. Examples run in
CI against stub models. First public release is **v0.1.0** (three chemistries end to end with the benchmark);
**v1.0.0** is reserved for after external validation and the methods preprint. A Zenodo DOI is minted on the
first tagged release.

---

# PART III — ACCEPTANCE, RISKS, AND SEQUENCING

## 16. Definition of done for v0.1.0
- A ClinVar variant, supplied by accession, flows end to end to a ranked candidate menu spanning every
  eligible chemistry (nuclease, base, prime), each candidate carrying a calibrated efficiency interval, a
  predicted outcome distribution, and an ancestry-stratified population/haplotype-aware off-target report,
  with complete provenance — reproducible from config + seed.
- The reference-bias / `rs114518452` off-target case is reproduced as an integration test and a documented
  example.
- The prime-editing path demonstrably unifies all four axes (variant input, ML efficiency with OOD honesty,
  outcome/byproduct prediction, population-aware off-target).
- CRISPR-Bench publishes at least the Cas9-efficiency, PE-efficiency, and off-target tasks with frozen
  splits, calibration metrics, and a working leaderboard.
- Library, CLI, and web all exercise the same core; CI is green across lint, type, test, Rust, docs, and
  benchmark smoke; v0.1.0 is on PyPI + conda + Docker with a Zenodo DOI.

## 17. Risk register & pivots
- **A competitor ships an integrated four-axis tool first.** Pivot emphasis to CRISPR-Bench (benchmark +
  model zoo + leaderboard) as the primary contribution; it is valuable regardless and harder to duplicate.
- **Foundation models prove strongly zero-shot for guide efficiency.** Refocus on FM + lightweight adapters;
  the swap-able `SequenceEmbedder`/`Scorer` interfaces already allow this.
- **Cross-cell-type generalization stays poor.** A field-wide reality, not an AlleleForge failure; lean
  harder on honest OOD flagging and calibrated uncertainty, and make the cross-context benchmark splits a
  headline feature.
- **Upstream model licenses block bundling.** The model-zoo license gate already prevents vendoring; fall
  back to runtime fetch with consent and document the constraint in the model card.

## 18. Recommended build sequence (summary)
0 → 1 → 2 → 3 → 4 → 5 (safety core) → 6 (ML substrate) → 7 (prove the vertical slice on nuclease) → 8 (base)
→ 9 (prime — the flagship) → 10 (designer) → 11 (report) → 12 (CLI) → 13 (web) → 14 (CRISPR-Bench, can run in
parallel from Phase 6 onward) → 15 (docs + release).

Phases 0–5 must precede all chemistry work. Phase 6 must precede 7–9. CRISPR-Bench (14) can begin once Phase
6's `Scorer` protocol is stable. Do not promise clinical applicability anywhere; AlleleForge generates
rigorously uncertain hypotheses, and that honesty is the product.

---

*End of specification. This document is the contract. When a decision not covered here arises, prefer the
option that maximizes reproducibility, honest uncertainty, and population-aware safety — in that order.*
