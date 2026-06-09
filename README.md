<div align="center">

# AlleleForge

**Variant in, corrective edit out.**

A variant-driven, multi-modality, uncertainty-aware CRISPR guide &amp; edit design framework —
across SpCas9 nuclease, base editors, and prime editors, with **population-aware** off-target
nomination and a public benchmark.

[![CI](https://github.com/clay-good/alleleforge/actions/workflows/ci.yml/badge.svg)](https://github.com/clay-good/alleleforge/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Typed: mypy strict](https://img.shields.io/badge/typed-mypy%20strict-blue.svg)](https://mypy-lang.org/)
[![Code style: ruff](https://img.shields.io/badge/lint-ruff-purple.svg)](https://github.com/astral-sh/ruff)

</div>

---

> [!WARNING]
> **AlleleForge is a research tool. It is not a medical device and does not provide medical advice.**
> It produces ranked, explicitly *uncertain* design hypotheses. Every off-target nomination it makes is
> **computational** and **must be experimentally validated** before any wet-lab or therapeutic use.
> See [Scope &amp; responsible use](#scope--responsible-use).

---

## Why AlleleForge

Most monogenic disease is, in effect, a copy-paste error at the allele level. The job of a genome editor
is to forge the corrective edit. Today that job is fragmented across a dozen single-purpose tools — one to
pick a guide, another to predict efficiency, a third to enumerate prime-editing extensions, a fourth to scan
for off-targets — none of which speak the same language and few of which agree on what "uncertain" means.

AlleleForge unifies the journey behind **one typed interface**: you supply a variant, it returns a ranked,
safety-annotated menu of candidate edits spanning every applicable modality, each carrying a **calibrated
uncertainty interval**, a **predicted edit outcome**, and a **population- and haplotype-aware off-target
report**.

### The four-axis gap it fills

For prime editing in particular, no existing open-source tool combines all four of:

| Axis | PRIDICT2.0 | PrimeDesign / PrimeVar | CRISPRme | **AlleleForge** |
|---|:---:|:---:|:---:|:---:|
| Therapeutic **variant** front-end | ✗ | ✓ | ✗ | ✓ |
| **ML efficiency** with calibrated uncertainty | ✓ | ✗ | ✗ | ✓ |
| **Outcome / byproduct** prediction | partial | ✗ | ✗ | ✓ |
| **Population-aware** off-target | ✗ | ✗ | ✓ | ✓ |

AlleleForge's contribution is to **wrap the best existing models** (PRIDICT2.0, BE-Hive, BE-DICT, inDelphi,
Cas-OFFinder, …) behind a unified, typed, uncertainty-honest interface and add value at the seams.

---

## Design principles

1. **Variant-first.** The canonical journey starts from *what is broken*, not from a guide.
2. **Honest uncertainty.** Every numeric prediction ships with a calibrated interval. No scorer returns a bare float.
3. **Population-aware by default.** Reference-only off-target analysis is a known safety gap (the Casgevy /
   BCL11A `rs114518452` case is the canonical cautionary tale). AlleleForge searches population variation by default.
4. **Wrap, don't rebuild.** Integrate proven tools; add new ML only at genuine coverage gaps.
5. **Reproducible to the byte.** Pinned environments, versioned datasets, deterministic seeds, content-hashed checkpoints.
6. **Three audiences, one core.** The library is the source of truth; CLI and web are thin shells over it.
7. **Typed and tested.** `mypy --strict`, `ruff`, and Hypothesis property tests on all core logic.
8. **Cite everything.** Every dataset, model, and scoring function carries a literature citation and a version.

---

## Design decisions

The principles above are realized by a handful of concrete, non-obvious engineering
tradeoffs. Each was chosen to maximize **reproducibility, honest uncertainty, and
population-aware safety — in that order**; the rationale and the code that enforces it:

| Decision | Why — and where it lives |
|---|---|
| **Weight-free stubs are the CI default; real weights are opt-in** (`real_weights` marker) | The full gate (lint, type, test, docs, examples, reproduce) runs with no GPU, network, or torch, so any contributor reproduces it byte-for-byte. The consent/license/checksum flow is still exercised in CI with an **injected downloader**; only the tensor load / forward pass is gated. See [`SPEC_V2.md`](SPEC_V2.md) R1. |
| **An unverifiable artifact is refused, never fetched** | A `null` checkpoint/dataset hash *blocks* the download by design — you cannot silently load an unpinned weight or dataset. The pin is a content hash, never a mutable tag. ([`model_zoo/loader.py`](src/alleleforge/model_zoo/loader.py), R0/R1.) |
| **FM-index auto-engages per region past 1 Mb** (`FM_INDEX_AUTO_THRESHOLD`) | Building the index has a fixed cost that only amortizes at contig scale; below the threshold the linear PAM pass wins. The result is byte-identical either way (parity-pinned). ([`offtarget/engine.py`](src/alleleforge/offtarget/engine.py).) |
| **The k-mer seed prefilter engages only when `k ≥ 5`** (`MIN_SELECTIVE_K`) | Honest micro-benchmark finding: a 4-letter alphabet saturates short k-mers, so a short seed prunes almost nothing and only adds overhead. `k ≥ 5` (low edit budget) measures ~2–4×; at the default ≤4-mismatch+bulge budget the seed is too short, so the FM-index stays the genome-scale path. ([`offtarget/_search.py`](src/alleleforge/offtarget/_search.py), R2.) |
| **Every native kernel keeps a parity-tested pure-Python fallback; the library never *requires* the crate** | `prefer_native` selects Rust when built; CI runs the off-target engine on **both** paths. Trades raw speed-when-unbuilt for "installs and passes anywhere; native is a pure bonus." ([`SPEC_V2.md`](SPEC_V2.md) R2.) |
| **Off-target nomination is an OR of two thresholds** (CFD ≥ 0.20 **or** MIT ≥ 0.10), and **both** scores are recorded per site | Two complementary specificity models catch different failure shapes; recording both (`OffTargetSite.mit_score`) keeps a MIT-nominated, low-CFD site auditable rather than mysteriously retained. ([`offtarget/scoring.py`](src/alleleforge/offtarget/scoring.py).) |
| **Ancestry risk is the worst-affected population, never the average; "carrying" means at/above the MAF threshold** | Averaging hides risk concentrated in one ancestry — the BCL11A cautionary tale. The carrying threshold is applied **identically** on the population and haplotype paths, so a trace, sub-threshold frequency cannot inflate the per-ancestry burden. ([`types/offtarget.py`](src/alleleforge/types/offtarget.py).) |
| **The cross-run off-target cache is safety-gated** to reference-only, default-scorer searches | A wrong off-target report is a *missed danger*, so a possibly-stale entry is never served once population / haplotype / patient augmentation is present (the key cannot fully capture that external data). ([`offtarget/cache.py`](src/alleleforge/offtarget/cache.py), R4.) |
| **Intervals are recalibrated by split-conformal; probabilities by isotonic regression** | Different calibration targets need different tools — a finite-sample coverage guarantee for regression intervals, monotone probability calibration for classification — with `empirical_coverage` / ECE flagging when each is needed. ([`scoring/uncertainty.py`](src/alleleforge/scoring/uncertainty.py), R5.) |
| **The default backbone is non-commercial, and the license gate enforces it** | Nucleotide Transformer v2 (500M) is **CC-BY-NC-SA-4.0** — loadable for research, *refused for commercial use* at load time. Real weights are never vendored. ([`model_zoo/cards/`](src/alleleforge/model_zoo/cards/), R1.) |
| **Results, splits, and caches are content-addressed** | A published benchmark number cannot be silently edited (each result carries a `signature`); a split pins both its dataset-content hash and its own membership hash, re-verified on read (`SplitIntegrityError` on drift). ([`benchmark/`](src/alleleforge/benchmark/).) |

---

## Architecture

AlleleForge is strictly layered: lower layers know nothing about higher ones. The **Designer** is the only
component that sees the whole pipeline; every domain service is independently testable and usable.

```mermaid
flowchart TB
    subgraph I["Interfaces"]
        PY["Python library"]
        CLI["aforge CLI"]
        WEB["Web UI (FastAPI + Next.js)"]
    end
    subgraph O["Orchestration"]
        DES["Designer: variant → routing → candidates → score → outcome → off-target → rank → report"]
    end
    subgraph D["Domain services"]
        VR["Variant resolver<br/>(HGVS, ClinVar)"]
        EN["Guide enumerators<br/>(cas9, base, prime)"]
        SC["Scoring<br/>(efficiency, outcome, uncertainty)"]
        OT["Off-target engine<br/>(population / haplotype)"]
    end
    subgraph F["Foundations"]
        GA["Genome access<br/>(FASTA, FM-index)"]
        DR["Data registry<br/>(DVC, gnomAD, ClinVar)"]
        MZ["Model zoo<br/>(ckpt hashing)"]
        CT["Core types and schemas"]
    end
    RUST["Rust / PyO3 — aforge_native: BWT off-target search · k-mer hashing · haplotype walking"]

    I --> O --> D --> F
    OT -.calls.-> RUST
    EN -.calls.-> RUST
```

### The variant-first journey

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant R as Resolver
    participant Rt as Router
    participant E as Enumerators
    participant S as Scorers
    participant X as Off-target engine
    participant K as Ranker

    U->>R: ClinVar / rsID / HGVS / VCF / coords
    R->>Rt: normalized Variant and consequence
    Rt->>E: eligible chemistries (nuclease / base / prime)
    E->>S: candidate guides and pegRNAs
    Note over S: efficiency and outcome (calibrated Prediction)
    E->>X: spacers and nicks
    Note over X: reference, then population, then haplotype, then patient VCF
    S->>K: scored candidates
    X->>K: ancestry-stratified off-target reports
    K-->>U: RankedMenu (Pareto front, provenance, disclaimer)
```

---

## Build status &amp; roadmap

AlleleForge is built in ordered phases (see [`SPEC.md`](SPEC.md), the authoritative build contract). Phases
0–5 establish the spine before any modality or ML code.

| Phase | Component | Status |
|---|---|:---:|
| 0 | Repo bootstrap, CI, packaging, Rust toolchain | ✅ done |
| 1 | Core domain types &amp; schemas (`types/`) | ✅ done |
| 2 | Genome access &amp; indexing (`genome/`) | ✅ done |
| 3 | Data registry &amp; population datasets (`data/`) | ✅ done |
| 4 | Variant resolver (`variant/`) | ✅ done |
| 5 | Off-target engine — population &amp; haplotype aware (`offtarget/`) | ✅ done |
| 6 | Scoring foundations: model zoo, embeddings, uncertainty (`scoring/`, `model_zoo/`) | ✅ done |
| 7 | Chemistry: SpCas9 nuclease (`enumerate/`, `scoring/`, `design/`) | ✅ done |
| 8 | Chemistry: base editing — ABE / CBE (`enumerate/`, `scoring/`, `design/`) | ✅ done |
| 9 | Chemistry: prime editing — the flagship (`enumerate/`, `scoring/`, `design/`) | ✅ done |
| 10 | Designer: routing, candidate menu, ranking (`design/`) | ✅ done |
| 11 | Reporting &amp; oligo output (`report/`) | ✅ done |
| 12 | CLI (`aforge`) (`cli/`) | ✅ done |
| 13 | Web UI &amp; API (`web/`) | ✅ done |
| 14 | CRISPR-Bench: tasks, frozen splits, metrics, runner, leaderboard (`benchmark/`) | ✅ done |
| 15 | Docs, runnable examples, release engineering (`docs/`, `examples/`) | ✅ done |

All fifteen v0.1.0 phases are complete. **Post-v0.1.0 work to "bake" the release toward v1.0 is tracked
in [`SPEC_V2.md`](SPEC_V2.md)**:

| Track | Scope | Status |
|---|---|:---:|
| R0 | Release hardening: pin real artifact hashes; supply-chain; reproducibility audit | ◐ in progress |
| R1 | Real-weights model integration through the consent-gated model zoo | ◐ in progress |
| R2 | Native `bwt`/`kmer`/`haplotype` kernels wired onto the off-target hot paths | ◐ in progress |
| R3 | External-tool adapters (Cas-OFFinder, VEP, HGVS) behind the registry | ◐ in progress |
| R4 | Scale: whole-genome on-disk FM-index (SA-IS), cohort throughput, cross-run caches | ◐ in progress |
| R5 | Validation, calibration study (ECE on real data), methods preprint | ◐ in progress |
| R6 | v1.0 release criteria | ☐ not started |

**Landed since v0.1.0.** R0 — Dependabot across pip/cargo/actions, a CI `pip-audit`+`cargo audit`
job, a CycloneDX SBOM on release, and a `scripts/reproduce.py` reproducibility audit gated in CI.
R1 — the consent/license/checksum resolution wired for the backbone and every trained scorer through
a shared `WeightGate`, plus a backbone **ONNX export** path (`export_onnx`, dynamic batch/sequence
axes, opset 17) for portable inference (the trained forward pass and the export both stay
`real_weights`-gated), and each menu's `provenance.models` now records the card-backed
`ModelCheckpoint` of **every model invoked** (deduped, scoped to the eligible chemistries, rendered in
the report footer, and captured by the reproducibility golden). R2 — **all three spec
kernels (`bwt`/`kmer`/`haplotype`) are now on their hot paths**: a **true-linear SA-IS**
FM-index build, a native k-mer seed kernel, **FM-index seed-and-extend wired into the engine's
reference scan** (auto-engaged past 1 Mb, byte-identical to the linear scan), and a **native
haplotype-walk kernel** that materializes each common haplotype's alternative sequence (~4x, pinned
byte-for-byte to the Python fallback). R3 — **the three external-tool adapters are now real** behind
recorded-fixture tests: **Cas-OFFinder** (input-deck builder + legacy/bulge output parser +
injectable-runner cross-check), **VEP** (region-endpoint predictor with an injectable fetcher, MANE
selection, and `(variant, assembly, transcript)` caching), and **HGVS** (`HgvsLibraryProjector` over
the real `hgvs`/UTA/SeqRepo stack) — with live network/binary calls factored behind injection points
(`live_integration`-marked, opt-in, never run in CI). R4 — **cohort-scale batch design**
(`design.design_many`) streams a whole VCF/iterable through `design` with **bounded memory** (each
menu summarized then released; `O(1)` with `on_result`), a **resumable JSONL run manifest** (a re-run
skips recorded items), per-item failure isolation, and an optional thread-parallel path — fed by the
**`cyvcf2` fast path** (`variant.iter_vcf`) that streams a VCF into the cohort (one record per concrete
ALT, multi-allelic split, non-`PASS`/symbolic dropped; injectable reader, CI-tested without htslib);
and **content-addressed cross-run caches** (`alleleforge.cache`) that memoize embeddings
(`CachedEmbedder.persistent`) and the reference off-target scan (`OffTargetCache` via
`search(..., cache=...)`, safety-gated to the default-scorer reference-only case) to disk so a value
computed in one run is reused by the next; and a **persistent, memory-mapped whole-genome FM-index**
(`genome.GenomeIndex`) — driven by R2's native SA-IS so the on-disk build scales to whole
chromosomes, consumed by the engine via `search(..., genome_index=...)`, built once and reused across
runs (parity-tested vs the per-call build; scale-tested on a downsampled chromosome in CI). R5 — the
**calibration & generalization machinery**: `scoring.ConformalCalibrator` recalibrates predictive
*intervals* to a target coverage with the finite-sample split-conformal guarantee (the regression
analog of isotonic), `benchmark.generalization_gap` quantifies the **cross-cell-type generalization
gap** (in-context vs held-out cell type, oriented so positive = worse), and
`scripts/calibration_study.py` regenerates the per-task-ECE + gap + recalibration report from
CRISPR-Bench (the real-data numbers fill in with R1); and the **methods-preprint draft**
([`docs/paper/preprint.md`](docs/paper/preprint.md)) turns the outline into a full manuscript —
abstract, methods, benchmark design, the weight-free end-to-end results (reference-bias reproduction +
the split-conformal coverage table), and reproducibility — with the accuracy-vs-published numbers
marked `[pending R1]`; and **reproducible SVG figures** (`alleleforge.viz`, a dependency-free hand-rolled
renderer) for the reference-bias reproduction, conformal coverage, per-task ECE, and the generalization
gap — committed under `docs/assets/figures/`, embedded above and in the preprint, regenerated byte-for-byte
by `make figures`. The one remaining R0 item is pinning the real
artifact hashes, which requires freezing the published upstream artifacts; the consent gate already
refuses any `null`-hash fetch by design.

---

## Install

> AlleleForge targets **Python ≥ 3.11**. The core install is deliberately light; heavy scientific, ML, and
> web stacks live in optional dependency groups so the base package installs fast and CI stays reliable.

```bash
# Core library (light: pydantic types, config, model-card parsing — no torch/numpy)
pip install alleleforge            # once published to PyPI

# From source, with the optional groups you need
git clone https://github.com/clay-good/alleleforge
cd alleleforge
pip install -e ".[core,genome,variant,cli,ml,dev]"
```

### Optional dependency groups

| Group | Pulls in | Needed for |
|---|---|---|
| `core` | polars, pyarrow, numpy | tabular I/O |
| `genome` | pyfaidx, pysam, cyvcf2, mappy, pyliftover | reference access, indexing (Phase 2) |
| `variant` | hgvs | HGVS resolution (Phase 4) |
| `cli` | typer | the `aforge` command-line interface (Phase 12) |
| `web` | fastapi, uvicorn, httpx | the web API + served frontend (Phase 13) |
| `ml` | torch, transformers, lightning, scikit-learn | real embedding backbones (Phase 6+); the uncertainty core needs none of these |
| `docs` | mkdocs-material, mkdocstrings | documentation site |
| `dev` | ruff, mypy, pytest, hypothesis, maturin | development |

### Native acceleration (optional)

The performance kernels live in a PyO3 crate (`aforge_native`) built with
[maturin](https://github.com/PyO3/maturin). **All three spec kernels are implemented**, each behind a
correct pure-Python fallback and a byte-identical parity test, and each wired into its hot path:

| Kernel | What it does | Hot path | Parity test | Speedup |
|---|---|---|---|:---:|
| `bwt` | FM-index `build`/`count`/`locate`/`pam_sites` | reference scan (PAM seed-and-extend) | [`test_native.py`](tests/genome/test_native.py) | genome-scale |
| `kmer` | exact length-`k` seed positions | seed prefilter (high-stringency scans) | [`test_kmer.py`](tests/offtarget/test_kmer.py) | ~2–4x / ~5–6x lookup |
| `haplotype` | apply a haplotype's variant set to a window | haplotype walk (stage 3 materialization) | [`test_haplotype_kernel.py`](tests/offtarget/test_haplotype_kernel.py) | ~4x |

`FMIndex.build(prefer_native=True)` transparently uses the Rust index when the crate is present; the
k-mer and haplotype dispatchers do the same. AlleleForge imports and runs cleanly **without** the crate
(pure-Python mode); build it for the genome-scale path:

```bash
pip install maturin
cd rust && maturin develop --release      # builds & installs aforge_native
```

`alleleforge._native.NATIVE_AVAILABLE` reports whether the compiled extension is present, and
`alleleforge.genome.native_fm_available()` whether the FM-index kernels specifically are built. The
native suffix array is built by **SA-IS** (`sais.rs` — Nong–Zhang–Chan induced sorting, `O(n)`) rather
than the direct sort's `O(n² log n)`, which collapses on the long poly-A / poly-N runs and tandem
repeats real genomes are full of; the unique sentinel keeps the suffix array unique so the result
stays byte-identical to the direct sort — pinned **directly** (the exposed `fm_suffix_array` vs the
ground-truth direct sort, over textbook-pathological and fuzz inputs) and end-to-end (FM-index
`count`/`locate` parity over low-complexity and random-long inputs).

That linear-time build is what makes the **whole-genome index** practical:
`genome.GenomeIndex.build_genome(reference)` persists one content-addressed FM-index per contig (both
strands) to disk and **memory-maps** it, so a genome index is built once, **survives across runs**
(a re-run maps the cache instead of rebuilding), and never pins itself in RAM. The off-target engine
takes it directly — `search(spacer, pam, reference=ref, genome_index=gi)` — anchoring PAMs through the
persistent index instead of rebuilding one per call, with hits identical to the per-call path
(parity-tested) and the memory-mapped query path validated at scale on a downsampled chromosome in CI.

---

## Quickstart

> The end-to-end design pipeline is **live**: `alleleforge.design.design()` resolves a variant, routes it
> to every eligible chemistry, enumerates and scores candidates, runs population-aware off-target, and
> returns a ranked, explained menu (see [the designer section](#the-designer-one-variant-every-chemistry-one-ranking-phase-10-shipping-now)),
> and [reporting & oligo output](#from-menu-to-bench-reporting--oligo-output-phase-11-shipping-now) renders it to
> cloning-ready oligos, HTML, PDF, JSON, and TSV. The whole pipeline is driven from the
> [`aforge` CLI](#the-aforge-cli-phase-12-shipping-now) and the
> [web API + browser UI](#web-ui--api-phase-13-shipping-now), and the same scorers are graded by
> [CRISPR-Bench](#crispr-bench-a-calibration-first-benchmark-phase-14-shipping-now). All fifteen build
> phases are complete; three [runnable example notebooks](#runnable-examples-phase-15) execute in CI, and
> the release pipeline (PyPI · multi-arch Docker · GitHub Release) is wired and tag-triggered. The snippets
> below show the lower-level building blocks the designer composes.

```python
from alleleforge.types import DNASequence, Prediction, UncertaintyMethod

seq = DNASequence("ACGTRYN")           # validates IUPAC alphabet
print(seq.reverse_complement())        # ambiguity-aware: R↔Y, N↔N → "NRYACGT"

# Every numeric prediction carries a calibrated interval, never a bare float.
p = Prediction(value=0.72, interval=(0.61, 0.83), method=UncertaintyMethod.ENSEMBLE,
               in_distribution=True, calibrated=True)
print(p.interval_level)                # 0.80 by default
```

**Resolve a variant** — every input form normalizes to one canonical, left-aligned record:

```python
from alleleforge.variant import resolve, RawTarget
from alleleforge.types import DNASequence

# A raw target sequence with a marked edit — no reference file needed.
rv = resolve(RawTarget(sequence=DNASequence("ACGTAACGTACGT"), position=4, ref="A", alt="G"))
print(rv.variant)            # target:4:A>G
print(rv.working_interval)   # 0-based half-open analysis window around it

# With a reference genome, indels are left-aligned and the asserted ref is
# validated against the build (a mismatch is a hard error — likely wrong build):
#   resolve("chr2:g.5226001del", reference=hg38, dbsnp=dbsnp_db)
#   resolve("VCV000012345", clinvar=clinvar_db)   # ClinVar accession → Variant
```

**Inspect the data registry** — every external dataset is versioned and license-aware:

```python
from alleleforge.data import DEFAULT_REGISTRY

print(DEFAULT_REGISTRY.names)                 # ('1000g', 'clinvar', 'dbsnp', 'encode', ...)
clinvar = DEFAULT_REGISTRY.get("clinvar")
print(clinvar.version, clinvar.license)       # 2024-05  public-domain (NCBI)
# Non-redistributable sources are never vendored; downloads are consent-gated
# and checksum-verified. See docs/data.md for the full provenance table.
```

The same journey from the `aforge` CLI (`pip install "alleleforge[cli]"`):

```bash
# Variant → ranked, safety-annotated menu, rendered as an interactive HTML report
aforge design VCV000012345 --reference-fasta hg38.fa \
    --intent correct --populations afr,eur,eas --format html --out report.html

# Standalone population/haplotype-aware off-target for a spacer. Every engine knob is
# tunable: the bulge budget, the CFD/MIT reporting thresholds, and the carrying MAF.
aforge offtarget GACGGAGGCTAAGCGTCGCAA --reference-fasta hg38.fa --pam NGG --json \
    --dna-bulges 1 --rna-bulges 1 --cfd-threshold 0.20 --mit-threshold 0.10 --maf 0.001

# Normalize any input form and show its class (debugging aid)
aforge resolve chr2:100:A>G --json
```

---

## The variant-first front end (Phases 2–4, shipping now)

Phases 2–4 implement everything from *an input* to *a validated, annotated variant with its genomic
context* — the foundation every modality plugs into.

```mermaid
flowchart LR
    subgraph IN["Accepted inputs"]
        A1["ClinVar accession"]
        A2["dbSNP rsID"]
        A3["HGVS g./c./p."]
        A4["VCF record"]
        A5["raw coordinates"]
        A6["raw target seq"]
    end
    R["resolve()"]
    subgraph NORM["Normalize"]
        N1["left-align + trim<br/>(bcftools-norm)"]
        N2["validate ref vs build<br/>(hard error on mismatch)"]
    end
    OUT["ResolvedVariant<br/>variant · working interval ·<br/>consequence · T2T recommendation"]

    A1 & A2 & A3 & A4 & A5 & A6 --> R --> NORM --> OUT
    R -. ClinVar/dbSNP/HGVS lookups .- DATA["Data registry<br/>(versioned, license-aware)"]
    NORM -. fetch + flag ambiguous loci .- GEN["Genome access<br/>(FASTA, FM-index, liftover)"]
```

**Coordinate convention cheat-sheet.** Internals are uniformly **0-based half-open**; only I/O
boundaries are 1-based. Every parser converts on read.

| Surface | System | Converted by |
|---|---|---|
| AlleleForge internals (`GenomicInterval`, `Variant.pos`) | **0-based half-open** | — (canonical) |
| ClinVar / gnomAD / dbSNP VCF | 1-based | `pos − 1` on read |
| GENCODE GTF | 1-based inclusive | `[start − 1, end)` on read |
| ENCODE bedGraph | 0-based half-open | unchanged |
| HGVS (`g.`), human-readable reports | 1-based | boundary helpers only |

**Dataset provenance** (pinned, versioned, citation-stamped — full table in [`docs/data.md`](docs/data.md)):

| Dataset | Version | License | Role |
|---|---|---|---|
| ClinVar | 2024-05 | Public domain | accession → variant + significance |
| gnomAD | v4.1 | CC0-1.0 | per-population allele frequencies |
| 1000 Genomes | phase 3 high-cov | Public (IGSR) | phased common haplotypes |
| HGDP | gnomAD v3.1 | CC0-1.0 | ancestry breadth |
| dbSNP | b156 | Public domain | rsID ↔ locus |
| GENCODE | v47 | Open | gene models / transcripts |
| ENCODE | 2024 | Open | chromatin tracks |

---

## The off-target engine (Phase 5, shipping now)

AlleleForge's safety core, and its clearest point of novelty: off-target nomination that is
**reference-, population-, and haplotype-aware** for every chemistry, behind one `search()` call that
returns an **ancestry-stratified** report. Reference-only off-target analysis has a known blind spot —
a minor allele can create a *de novo* PAM the reference never shows — and because allele frequencies
differ by ancestry, that blind spot concentrates risk in under-represented populations.

```mermaid
flowchart TB
    SP["spacer + PAM"] --> S1
    subgraph ENG["search() — five stages"]
        direction TB
        S1["1 · Reference scan<br/>PAM-anchored · ≤4 mismatch · ≤1 DNA + ≤1 RNA bulge · both strands<br/>FM-index seed-and-extend at genome scale (auto past 1 Mb)"]
        S2["2 · Population augmentation<br/>gnomAD alt-allele re-scan → de-novo PAMs / strengthened seed sites"]
        S3["3 · Haplotype walk<br/>common 1000G / HGDP haplotypes (variant combinations)<br/>native haplotype kernel materializes each alt sequence (~4x)"]
        S4["4 · Patient VCF (optional)<br/>personalize to one genome"]
        S5["5 · Score · threshold · de-dup · stratify"]
        S1 --> S5
        S2 --> S5
        S3 --> S5
        S4 --> S5
    end
    S5 --> R["OffTargetReport<br/>ancestry-stratified · every site tagged<br/>reference / population / patient + causal allele + freq"]
```

Every site records **where it came from** — the reference, a population variant (which allele, which
populations, at what frequency), or a patient's VCF — so a nomination can be audited, not trusted
blindly. The report's worst-case is computed against the **worst-affected ancestry**, never the
average, and it rolls every site into one **aggregate genome-wide specificity score**
(`specificity_score()`, see the cheat-sheet below).

A population is annotated as carrying a site **only at or above the MAF safety threshold** — applied
identically on the population-variant and haplotype paths, so the per-ancestry stratification can never
attribute a site's burden to a population that merely shows a trace, sub-threshold frequency. The
`populations` and `ancestries` provenance on each site are the *same* carrying set, by construction.

> [!NOTE]
> **k-mer seed acceleration (R2).** The scan carries an optional, **proven-equivalent** k-mer
> seed-and-extend prefilter (native Rust kernel + pure-Python fallback): by the pigeonhole bound, any
> in-budget alignment shares an exact length-`k` seed with the spacer, so anchors whose window contains
> no seed can be skipped without ever dropping a hit (an exhaustive randomized test pins seeded ≡
> brute-force). It **auto-engages only when the seed is selective** (`k ≥ 5`, i.e. high-stringency / low
> edit-budget scans) — measured **~2–4x** there ([`scripts/native_speedup.py`](scripts/native_speedup.py)) —
> and is a transparent no-op at the default ≤4-mismatch+bulge budget, where the FM-index remains the
> genome-scale path. See [`SPEC_V2.md`](SPEC_V2.md) R2.

> [!NOTE]
> **FM-index seed-and-extend on the reference scan (R2, landed).** Stage 1 now anchors PAMs through a
> content-addressed FM-index (`search(..., use_fm_index=...)`): each concrete PAM is *located* in the
> index (the PAM is the seed) and only those anchors are *extended* by the shared alignment, replacing
> the linear `O(n)` PAM pass. It returns **byte-identical hits** to the brute-force scan — pinned by a
> randomized parity test at both the `scan_sequence` and `search` levels — and **auto-engages per
> region past 1 Mb** (`FM_INDEX_AUTO_THRESHOLD`), so genome-scale contigs take the indexed path while
> small inputs stay on the linear scan.

### Reference bias, reproduced

The canonical cautionary tale is the BCL11A enhancer variant `rs114518452` (Cancellieri &amp; Pinello,
*Nat Genet* 2023). AlleleForge reproduces it as an integration test: a reference-only scan returns
**zero** sites, while the population-aware scan nominates the high-CFD off-target the minor allele
creates — ancestry-stratified, with its African-ancestry-enriched frequency recorded.

```python
from alleleforge.offtarget import search
from alleleforge.types.guide import PAM

report = search(spacer, PAM(pattern="NGG"), reference=hg38, gnomad=gnomad_db)
for site in report.sites:
    print(site.origin, round(site.score, 2), site.causal_allele, site.populations)
worst = report.worst_ancestry()        # ('afr', 1.0) — flagged, not averaged away
spec = report.specificity_score()      # aggregate genome-wide specificity in (0,1], 1.0 = clean
```

![Reference bias reproduced: a reference-only scan finds zero off-targets where the population-aware scan nominates one high-CFD site.](docs/assets/figures/reference_bias.svg)

*Every figure in this README is regenerated byte-for-byte from the weight-free,
deterministic pipeline by `python scripts/figures.py` — committed SVGs, no plotting
dependency (the same hand-rolled-renderer discipline as the PDF report).*

### Specificity scoring cheat-sheet

| Score | Source | Status in AlleleForge |
|---|---|---|
| **MIT / Hsu** | Hsu et al., *Nat Biotechnol* 2013 | Exact — published 20-position weight table |
| **CFD** | Doench et al., *Nat Biotechnol* 2016 | Published PAM table; mismatch weights default to a transparent seed model, **injectable** with the exact Doench matrix |
| **CFD-Cas12a** | analog | Seed at the PAM-proximal 5' end, `TTTV` PAM |

Those score one **site**. The report also rolls every site into one **aggregate genome-wide specificity
score** — `report.specificity_score()`, the CFD-scale analog of the Hsu 2013 / MIT guide score
`100/(100+Σ)`, i.e. `1/(1 + Σ site scores)` ∈ (0, 1], **1.0** for a guide with no off-targets and
decreasing as the total burden grows. It is the single number every design tool headlines, and unlike the
worst-case it **distinguishes two guides with the same worst site but a different *number* of off-targets**.
It surfaces on **every output surface that summarizes off-target**: the HTML/PDF report and the
`CandidateReport.offtarget_specificity` export field, the standalone `aforge offtarget` command and its
`POST /api/offtarget` web equivalent (both alongside the site count and worst-case score), and the cohort
batch summary (`best_specificity`), so triage can rank by total burden, not just the single worst site.

All three site scores sit behind one swappable `OffTargetScorer` protocol, so a Phase 6 ML scorer drops in
without touching the engine. Reporting thresholds default to **CFD ≥ 0.20 or MIT ≥ 0.10** — an **OR**, so
a site can be nominated on its MIT score even when its CFD is sub-threshold. So that a nomination stays
auditable, every site records **both**: the primary `score` (under `score_method`) and the companion
`mit_score` (`OffTargetSite.mit_score`, `None` when MIT is undefined — a bulged or non-20-nt alignment).
The MIT score that retained a low-CFD site is therefore visible in the serialized report, never silently
dropped.

> The genome-scale search is the FM-index seed-and-extend path (native Rust `bwt` kernel when built, a
> *correct* pure-Python FM-index otherwise — byte-identical, pinned by parity tests; CI never blocks on
> the native build). It is wired into the engine's reference scan and auto-engages on large contigs.

### External-tool adapters (R3)

AlleleForge is **independent** of external tools but integrates them at the seams, each behind a
swappable interface so its absence degrades gracefully and its presence adds a cross-check or a
richer annotation. Every adapter is tested against **recorded fixtures**; only the live network/binary
call is opt-in (`live_integration`-marked, never run in CI).

| Adapter | Role | Pure (CI-tested) | Live (opt-in) |
|---|---|---|---|
| **Cas-OFFinder** | off-target cross-check vs. the native engine | input-deck builder, legacy/bulge output parser, `disagreements()` | the binary subprocess (injectable `runner`) |
| **VEP** (Ensembl REST) | molecular consequence for chemistry routing | `parse_vep_response` (MANE/canonical selection, SO term → impact), `(variant, assembly, transcript)` cache | the region-endpoint GET (injectable `fetcher`) |
| **HGVS** (`hgvs`/UTA/SeqRepo) | `c.`/`p.` ⇄ `g.` projection | dependency-free `g.` parser; import-guarded `HgvsLibraryProjector` | `AssemblyMapper.c_to_g` against UTA |

Disagreements are **surfaced as flags, never hidden**: a Cas-OFFinder locus the native engine misses
(or vice versa) is reported, not silently dropped.

---

## The scoring substrate (Phase 6, shipping now)

Before any chemistry-specific predictor, AlleleForge establishes the reusable ML substrate: a
**license-gated model zoo**, a **swappable embedding backbone**, and the **calibrated-uncertainty**
machinery that realizes the honest-uncertainty principle. The whole substrate is pure stdlib in its
core path — no numpy or torch — so it runs in CI on a weight-free stub embedder; real 500M-parameter
backbones are gated behind the `real_weights` marker.

```mermaid
flowchart LR
    SEQ["DNA sequence"] --> EMB["SequenceEmbedder<br/>(NT v2 · Caduceus · Evo 2 · Stub)"]
    EMB --> CACHE["embedding cache<br/>(by sequence hash)"]
    EMB --> OOD["OODDetector<br/>distance vs training reference"]
    CACHE --> MODEL["scorer / ensemble"]
    MODEL --> U{"uncertainty"}
    U -->|N=5 default| ENS["deep ensemble<br/>mean ± z·σ (disagreement)"]
    U -->|fallback| EV["evidential<br/>aleatoric + epistemic"]
    U -->|if quantiles| QT["quantile interval"]
    ENS & EV & QT --> CAL["isotonic calibration<br/>(reduces ECE)"]
    OOD --> CAL
    CAL --> PRED["Prediction[float]<br/>value · 80% interval · method ·<br/>in_distribution · calibrated"]
```

**No bare floats.** Every scorer returns a `Prediction`, never a number; `ensure_prediction` is the
runtime guard at the orchestration seam. **No undocumented models.** Every checkpoint loads through the
model zoo, which refuses a missing card, a license that forbids the use, or an unverifiable hash, and
surfaces a `ModelCheckpoint` into result provenance.

**Consent-gated real weights (R1).** Every trained model — the sequence backbone **and** the
per-chemistry adapters (cas9 efficiency/outcome, base-edit outcome, prime efficiency) — resolves its
weights through one shared gate, `model_zoo.loader.WeightGate`, not a bare `from_pretrained`:
`resolve_weights()` runs the **license gate** (the default Nucleotide Transformer v2 is **CC-BY-NC-SA**
and the trained adapters are research-only — all refused for commercial use), **requires explicit
consent** before any download, **checksum-verifies** a pinned artifact, and records the resolved
`ModelCheckpoint` for provenance (e.g. `EnsembleEfficiencyScorer.backbone_checkpoint()`). The whole
consent/license/checksum flow is exercised in CI with an injected downloader — no network, no torch;
only the tensor load / forward pass itself stays behind the `real_weights` marker. Every model ships a
bundled, license-gated card. Each menu's `provenance.models` records the card-backed `ModelCheckpoint`
of **every model invoked** — deduped, scoped to the chemistries that ran, and rendered in the HTML/PDF
report footer — so a result names the exact models that produced it. The checkpoint carries the card's
`known_failure_modes` alongside its name, version, license, and citation, so the provenance is
**self-contained for safety audit**: a consumer can check a design against what each model is documented
to get wrong without re-opening the cards. See [`SPEC_V2.md`](SPEC_V2.md) R1.

### Uncertainty method cheat-sheet

| Method | Role | Interval |
|---|---|---|
| **Deep ensemble** (N=5) | default | `mean ± z·σ` from member disagreement — **widens on OOD** |
| **Evidential** (NIG) | single-model fallback | splits aleatoric (data) vs epistemic (model) variance |
| **Quantile** | when the model emits quantiles | read off the `(1±level)/2` quantiles |
| **Isotonic calibration** | post-hoc, recalibrates *probabilities* | PAV fit; `expected_calibration_error` quantifies the gain |
| **Conformal recalibration** | post-hoc, recalibrates *intervals* | split-conformal width scale to a target coverage (finite-sample guarantee); `empirical_coverage` flags when it's needed |

```python
from alleleforge.scoring import DeepEnsemble, ensemble_prediction, OODDetector, StubEmbedder

ens = DeepEnsemble([m1, m2, m3, m4, m5])                 # five members
emb = StubEmbedder().embed(["GACCATGCAACCTTGAACGT"])[0]   # NT v2 in production
ood = OODDetector(training_reference)                     # embedding-space density
pred = ensemble_prediction(ens.predict(features), in_distribution=ood.is_in_distribution(emb))
print(pred.value, pred.interval, pred.method, pred.in_distribution)   # honest by construction
```

---

## The first chemistry: SpCas9 nuclease (Phase 7, shipping now)

The most mature chemistry, and the right one to prove the **full vertical slice** end to end. From a
resolved variant, `design_cas9` enumerates guides, scores efficiency and outcome with calibrated
uncertainty, runs the population-aware off-target engine, and returns ranked candidates.

```mermaid
flowchart LR
    V["ResolvedVariant<br/>+ intent"] --> EN["enumerate_cas9<br/>PAM-anchored · strand-aware ·<br/>cut 3 bp 5' of PAM · actionable window"]
    EN --> EF["efficiency<br/>RS3 baseline / deep ensemble<br/>(80% interval + OOD)"]
    EN --> OUT["outcome<br/>microhomology / MMEJ +<br/>1-bp insertion spectrum"]
    EN --> OT["off-target<br/>(Phase 5 engine,<br/>ancestry-stratified)"]
    EF & OUT & OT --> C["DesignCandidate[]<br/>ranked: efficiency then safety"]
    EN -.precise intent.-> HDR["HDR donor template"]
```

**Defaults & decisions.** Primary PAM `NGG`; `NG` (SpCas9-NG) and `NRN`/`NYN` (SpRY) are emitted only
when no `NGG` guide is actionable **and** opted in. Cut site 3 bp 5' of the PAM. The actionable window
is tight around the edit for precise intents (HDR efficiency falls off with cut-to-edit distance) and
the whole working interval for a knock-out, which marks frameshift outcomes as intended.

| Axis | Default (CI, weight-free) | Trained alternative (model zoo, `ml` extra) |
|---|---|---|
| Efficiency | RS3-style feature baseline + backbone deep ensemble | Rule Set 3; fine-tuned NT v2 ensemble |
| Outcome | microhomology/MMEJ + 1-bp insertion model | inDelphi (default) · Lindel · X-CRISP + agreement |
| Off-target | Phase 5 engine (pure-Python fallback) | Phase 5 engine (Rust FM-index) |

Every efficiency score carries an 80% interval and an OOD flag; every outcome is a normalized
distribution over indel alleles; every candidate carries an ancestry-stratified off-target report —
so a ranked menu is honest about what it does and does not know.

---

## Base editing: the bystander problem (Phase 8, shipping now)

Base editors install a single transition (ABE: A·T→G·C; CBE: C·G→T·A) without a double-strand break,
within a narrow activity window. The hard part is the **window outcome**: of the editable bases in the
window, which get edited — and what *bystanders* ride along. AlleleForge enumerates every sgRNA placing
the target base in-window per editor, predicts the window-allele distribution, and ranks by the
probability of the **exact** intended allele while minimizing bystander burden.

```mermaid
flowchart LR
    V["ResolvedVariant<br/>(transition SNV)"] --> EL{"editor eligible?<br/>ABE: A·T→G·C<br/>CBE: C·G→T·A"}
    EL --> EN["enumerate_base_edits<br/>target base in window 4–8 ·<br/>strand-aware · bystanders flagged"]
    EN --> WO["window outcome<br/>per-position p(edit) × motif →<br/>2ᵏ allele distribution"]
    WO --> M["p_intended_exact<br/>+ bystander_burden"]
    EN --> OT["off-target<br/>(Phase 5, ancestry-stratified)"]
    M & OT --> C["DesignCandidate[]<br/>ranked: clean-edit then bystander<br/>cleanest = recommended"]
```

**Declarative editor registry.** ABE8e, CBE4max, and evoCDA1 ship as data; adding an editor (deaminase,
chemistry, window, PAM, motif preference) is a one-descriptor change, not code.

| Editor | Deaminase | Edit | Window | Motif preference |
|---|---|---|:---:|---|
| **ABE8e** | TadA-8e | A→G | 4–8 | none (broad) |
| **CBE4max** | APOBEC1 | C→T | 4–8 | TC (prefers 5′ T) |
| **evoCDA1** | evoCDA1 | C→T | 2–10 | none (broad window) |

Every candidate carries the tradeoff explicitly — the `bystander-present:N` / `clean` flag, the full
window-allele distribution, an ancestry-stratified off-target report, and a **calibrated
`bystander_burden`** (the expected number of bystander edits, with an 80% interval) persisted as a
structured field on the candidate. The burden the ranking minimizes is therefore exportable, not just
printable: it rides through the JSON/TSV/Parquet exports (a `bystander_burden` column), the HTML/PDF
reports, and the cohort batch summary (`best_bystander_burden`), alongside the `p_intended_exact` it is
ranked against. The recommendation is the cleanest editor/guide combination, not just the first one found.

---

## Prime editing: the four-axis flagship (Phase 9, shipping now)

Prime editing is the chemistry where AlleleForge contributes the most. PRIDICT2.0 is SOTA for
efficiency but has no variant front-end and no off-target module; PrimeDesign/PrimeVar give
ClinVar-to-pegRNA but only rule-based scoring and reference-only off-target; CRISPRme does population
off-target but designs no pegRNAs. **AlleleForge stitches all four axes together and fills the seams.**

```mermaid
flowchart LR
    V["ResolvedVariant + intent"] --> EN["enumerate_prime"]
    EN --> G["pegRNA geometry:<br/>nick · PBS 8-17 · RTT 7-34 (edit + >=5 homology) ·<br/>tevopreQ1 epegRNA · PE3/PE3b nick"]
    G --> EF["efficiency<br/>PRIDICT2.0-style + ePRIDICT<br/>(80% interval, OOD flag)"]
    G --> OUT["outcome<br/>intended vs. byproduct<br/>(scaffold / partial RTT / indel)"]
    G --> OT["off-target on BOTH nicks<br/>pegRNA nick + ngRNA nick<br/>merged, ancestry-stratified"]
    EF --> C["DesignCandidate[] (ranked)"]
    OUT --> C
    OT --> C
```

| Axis | PRIDICT2.0 | PrimeDesign / PrimeVar | CRISPRme | **AlleleForge** |
|---|:---:|:---:|:---:|:---:|
| Therapeutic **variant** front-end | no | yes | no | **yes** |
| **ML efficiency** + calibrated uncertainty | yes | no | no | **yes** |
| **Outcome / byproduct** prediction | partial | no | no | **yes** |
| **Population-aware** off-target | no | no | yes | **yes** |

**Honest by construction.** PRIDICT2.0 is trained on HEK293T/K562; any other cell context flags the
efficiency prediction out-of-distribution and raises an `ood` flag rather than hiding it. The
off-target engine runs on the pegRNA nick **and** the ngRNA nick, merging into one ancestry-stratified
report. The PE3b nicking guide is preferred when a seed-disrupting ngRNA exists (it nicks only the
edited strand, suppressing indels). See the canonical journey end to end in
[`examples/01_clinvar_to_design.ipynb`](examples/01_clinvar_to_design.ipynb).

---

## The designer: one variant, every chemistry, one ranking (Phase 10, shipping now)

The keystone that realizes the variant-first promise end to end. `design()` takes any input form, decides
which chemistries can biologically make the edit, generates and scores candidates from each, ranks them on
**one footing**, and returns an explained `RankedMenu` with a Pareto front and full provenance.

```mermaid
flowchart LR
    V["variant input<br/>(any form)"] --> R["resolve()"]
    R --> RT["route()<br/>transparent rules:<br/>variant class + intent"]
    RT --> ABE["base ABE/CBE<br/>(transition SNV)"]
    RT --> PE["prime<br/>(precise small edit)"]
    RT --> NUC["nuclease<br/>(disruption intent)"]
    ABE & PE & NUC --> RANK["rank_candidates()<br/>weighted sum + Pareto front"]
    RANK --> M["RankedMenu<br/>ordered · rationale ·<br/>Pareto front · provenance"]
```

**Routing is transparent and inspectable.** Each rule is a chemistry paired with a one-line biological
rationale and a pure `(resolved, intent)` predicate. Adding or relaxing a rule is a one-line data change,
and `route()` explains every verdict — kept *and* dropped.

| Chemistry | Eligible when | Biological reason |
|---|---|---|
| Base editing (ABE) | transition SNV, required change `A:T→G:C` | one in-window transition, no double-strand break — the cleanest fix |
| Base editing (CBE) | transition SNV, required change `G:C→A:T` | same, complementary transition |
| Prime editing | any precise small edit (≤ RTT length), non-disruptive intent | arbitrary substitutions / short indels from an RTT template, no break |
| SpCas9 nuclease | disruption (knock-out) intent | a break repaired by NHEJ yields frameshifting indels |

**Ranking puts every chemistry on one footing.** Candidates are projected onto four shared,
higher-is-better objectives and ordered by a transparent weighted sum, with the Pareto front always
exposed for users who weight differently.

| Objective | Definition | Default weight |
|---|---|:---:|
| Efficiency | calibrated on-target efficiency point estimate | 0.35 |
| Cleanliness | probability mass on the intended allele | 0.30 |
| Safety | `1 − off-target score` of the **worst-affected ancestry** | 0.30 |
| Simplicity | reagent simplicity (single sgRNA > pegRNA + nick + motif) | 0.05 |

The safety term uses the **worst-affected ancestry**, never the average, so a guide safe on average but
dangerous in one population is correctly down-ranked. The designer **degrades gracefully**: an unavailable
model, a failing enumeration, or a chemistry that finds nothing is recorded with its reason in the menu
rationale while the rest of the menu still returns.

```python
from alleleforge.design import design, eligible_chemistries
from alleleforge.types.edit import EditIntent

# Which chemistries can even make this edit?
print(eligible_chemistries(resolved, EditIntent.CORRECT))   # [BASE_CBE, PRIME]

# One call: resolve → route → enumerate → score → off-target → rank.
menu = design("VCV000012345", reference=hg38, clinvar=clinvar_db,
              intent=EditIntent.CORRECT, populations=["afr", "eur", "eas"])
best = menu.best
print(best.chemistry, best.rationale)        # includes the score breakdown
print(menu.pareto_front)                      # trade-off-optimal candidates
print(menu.provenance.seed)                   # reproducible to the byte
print([m.name for m in menu.provenance.models])  # every model invoked, e.g. ['be-dict', 'pridict2']
```

### Cohort-scale batch design (R4)

`design_many` is the cohort multiplier over `design`, built so a whole VCF is no different from three
rows: it **streams** the input (bounded memory — each menu is summarized then released), is
**resumable** (a JSONL run manifest a re-run skips past), and **isolates per-item failures** (an
unresolvable variant is recorded, not fatal). `variant.iter_vcf` is the **cyvcf2 fast path** that
*produces* the lazy stream straight from a VCF.

```python
from alleleforge.design import design_many
from alleleforge.variant import iter_vcf

report = design_many(
    iter_vcf("cohort.vcf.gz"),     # streams a VCF: one record per concrete ALT, multi-allelic split,
                                   # symbolic/spanning alleles skipped, non-PASS dropped by default
    reference=hg38, intent=EditIntent.INSTALL,
    manifest_path="run.jsonl",     # resume point: a re-run skips items already recorded
    output_dir="menus/",           # durable per-sample menu JSON (survives the run)
    on_result=print,               # stream results → O(1) memory in cohort size
)
print(report.succeeded, report.failed, report.skipped)
```

`iter_vcf` also accepts any iterable duck-typed to the cyvcf2 `Variant` shape (a region query, a
generator, a test list), so the whole pipeline is testable without the native htslib dependency; a
path open names the `genome` extra in a clear error when `cyvcf2` is absent.

The same cohort run is one command from the [`aforge` CLI](#the-aforge-cli-phase-12-shipping-now) —
the `batch` subcommand auto-detects a VCF (cyvcf2 fast path) vs a one-variant-per-line list:

```bash
# Whole-VCF cohort → resumable run, durable per-sample menus, a per-item TSV summary
aforge batch cohort.vcf.gz --reference-fasta hg38.fa --intent correct \
    --manifest run.jsonl --output-dir menus/ --summary-tsv summary.tsv --max-workers 8
# Summary columns: best_chemistry · best_efficiency · best_bystander_burden · worst_offtarget · best_specificity · n_candidates
```

…and over HTTP from the [web API](#web-ui--api-phase-13-shipping-now): `POST /api/batch` takes a JSON
variant list and returns the same per-item summaries with provenance — cohort design reaches all three
audiences (library, CLI, web) over one core.

| Guarantee | How |
|---|---|
| **Bounded memory** | input consumed lazily; only the per-item menu is held, then released (`on_result` ⇒ `O(1)`) |
| **Resumable** | JSONL run manifest with a provenance header; a re-run skips recorded `item_id`s |
| **Failure-isolated** | a per-variant error is captured in the manifest; the cohort continues |
| **Parallel (safe)** | `max_workers` + a `reference_factory` (a pyfaidx handle is not thread-safe to share) |
| **VCF fast path** | `iter_vcf(path)` streams a VCF (cyvcf2), splitting multi-allelic rows and dropping non-`PASS`/symbolic calls — injectable, so CI-tested without htslib |
| **Auditable** | `CohortRunReport` carries run counts + provenance (version, seed, build, intent) |

### Content-addressed cross-run caches (R4)

A cohort recomputes the same embeddings and the same reference scans constantly. `alleleforge.cache`
is the cross-run memo: a sharded, **atomically-written** (temp-then-rename) disk key/value store under
the cache dir, keyed by the SHA-256 of the inputs that determine the result, so a value computed in
one run is reused by the next.

| Cache | Key | How to use | Safety |
|---|---|---|---|
| **Embeddings** | sequence hash, scoped per backbone identity | `CachedEmbedder.persistent(embedder)` | content-addressed; two backbones never collide |
| **Off-target** | spacer · PAM · budget · thresholds · reference (build + contig lengths) · regions | `search(..., cache=OffTargetCache())` | **only** the default-scorer, reference-only case is cached — gnomAD/haplotype/patient or a custom scorer bypasses it, so a danger scan is never served stale |

A wrong off-target report is a missed danger, so the off-target cache refuses to key anything it
cannot fully capture: a changed budget/PAM/threshold/reference is a new key, and any
population/haplotype/patient augmentation skips the cache entirely.

---

## From menu to bench: reporting & oligo output (Phase 11, shipping now)

A ranked menu is only useful if a bench scientist can order it and a pipeline can
parse it. Phase 11 turns a `RankedMenu` into the artifacts users actually consume —
**cloning-ready oligos**, a structured report model, machine-readable exports, an
**interactive HTML** page, and a **static print-ready PDF** — every render leading
with the research-use disclaimer and ending with full provenance. The whole phase
is **dependency-free**: no plotting library, no PDF toolchain, nothing for CI to
flake on.

```mermaid
flowchart LR
    M["RankedMenu"] --> B["build_report()"]
    B --> R["DesignReport<br/>disclaimer · candidates · provenance"]
    R --> OL["oligos_for()<br/>annealed duplexes, round-trip-checked"]
    R --> J["JSON / TSV / Parquet<br/>(machine-readable)"]
    R --> H["render_html()<br/>interactive Plotly, ancestry tables"]
    R --> P["render_pdf()<br/>print-ready, pure-Python"]
```

**Cloning oligos round-trip by construction.** `oligos_for(candidate)` dispatches
by chemistry; the cardinal invariant — enforced on build and re-checked by
`reconstruct()` — is that the oligos rebuild the intended spacer / RTT / PBS. A
design whose oligos do not reconstruct is a cloning error caught before synthesis.

| Chemistry | Oligos emitted | Default scheme |
|---|---|---|
| SpCas9 sgRNA | one duplex (vector 5' overhangs + U6 `G`) | lentiGuide BsmBI |
| Base-editor sgRNA | one duplex (standard sgRNA) | lentiGuide BsmBI |
| pegRNA | spacer duplex + 3' extension (RTT + PBS + epegRNA motif) + ngRNA duplex | pegRNA GG BsaI |

**Honest rendering.** HTML charts are interactive Plotly figures pulled from a CDN
with each figure's spec inlined as JSON — so no Python plotting dependency is
needed and **no sequence data leaves the page**. Off-target tables are
ancestry-stratified, surfacing the worst-affected population per candidate. The PDF
is a small self-contained writer (no weasyprint / reportlab) for a clean leave-behind.

```python
from alleleforge.report import build_report, render_html, render_pdf, report_to_tsv

report = build_report(menu, variant="chr11:5226778:T>A", intent="correct")
open("report.html", "w").write(render_html(report))     # interactive, self-contained
open("report.pdf", "wb").write(render_pdf(report))      # static, print-ready
open("menu.tsv", "w").write(report_to_tsv(report))      # one row per candidate
report.best.oligos.reconstruct()                         # ('spacer', 'rtt', 'pbs')
```

---

## The `aforge` CLI (Phase 12, shipping now)

A thin, reproducible, config-driven [Typer](https://typer.tiangolo.com/) shell over the library — **no
business logic of its own**. Every command resolves its inputs, calls the same functions the Python API
exposes, and can emit machine-readable JSON. Install with `pip install "alleleforge[cli]"`.

```mermaid
flowchart LR
    CFG["--config run.toml<br/>+ CLI flags + --seed"] --> CMD
    CMD["aforge subcommand"] --> RES["resolve"]
    CMD --> DES["design"]
    CMD --> BAT["batch (cohort)"]
    CMD --> OT["offtarget"]
    CMD --> DAT["data list/show"]
    DES --> R["library: resolve → design → report"]
    BAT --> MANY["library: iter_vcf → design_many"]
    MANY --> SUM["per-item summary (TSV/JSON)<br/>+ JSONL manifest · menus/"]
    R --> OUT["JSON · TSV · HTML · PDF<br/>+ .provenance.json sidecar"]
```

| Command | Purpose |
|---|---|
| `aforge resolve <input>` | Normalize any input form; show the canonical variant + class. |
| `aforge design <input>` | Variant → ranked, multi-chemistry menu rendered to JSON/TSV/HTML/PDF. |
| `aforge batch <vcf\|list>` | Cohort design over a VCF (cyvcf2 fast path) or variant list — streaming, resumable, failure-isolated. |
| `aforge offtarget <spacer>` | Standalone population/haplotype-aware off-target search. |
| `aforge data list` / `show <name>` | Inspect the dataset registry (versions, licenses, provenance). |
| `aforge bench list` / `run` | List and run CRISPR-Bench tasks against frozen splits. |
| `aforge bench leaderboard <result.json…>` | Aggregate signed results into the model-card-gated leaderboard (Markdown/HTML). |

Global options sit before the subcommand (`--seed`, `--reference`, `--cache-dir`, `--verbose`,
`--version`); every command takes `--json`. **Exit codes are distinct and scriptable**: `0` success,
`2` usage/input error, `3` missing data (e.g. reference FASTA not found), `4` an unavailable model or
feature. A run is reproducible from its echoed `--seed` + config (byte-identical modulo the UTC
timestamp), and a `<output>.provenance.json` sidecar is written next to every file output.

```bash
# Reproducible design from a config file; CLI flags override the file
aforge --seed 20240501 design chr2:71:A>C \
    --reference-fasta hg38.fa --config run.toml \
    --chemistry prime --weights 0.5,0.2,0.2,0.1 --format html --out report.html
# → wrote report.html and report.html.provenance.json
```

---

## Web UI & API (Phase 13, shipping now)

The accessible front door for users who will not touch a terminal: a **FastAPI** backend that exposes the
library over HTTP, and a **dependency-free served single-page frontend** that drives the variant-first
journey in the browser — with a **single-variant** tab and a **cohort (batch)** tab that posts a variant
list to `/api/batch` and renders the per-item summary table. The app is a thin async layer with **no
business logic of its own** — it validates each request with a pydantic model, calls the same functions the
Python API and CLI use, and returns a Phase 1 / Phase 11 schema-validated response, with OpenAPI
auto-generated at `/docs`.

```mermaid
flowchart LR
    B["Browser SPA<br/>(served, no Node build)<br/>single · cohort tabs"] -->|POST /api/design · /api/batch| API
    CURL["curl / httpx / any client"] -->|JSON| API
    subgraph API["FastAPI app (local)"]
        EP["resolve · design · batch · offtarget<br/>data · bench · health · jobs"]
        JQ["in-process async job queue<br/>(thread worker + progress)"]
        EP --> LIB
        JQ --> LIB
    end
    LIB["library: resolve → design → report"] --> OUT["JSON · HTML · PDF<br/>(Phase 1 / Phase 11 schemas)"]
```

> [!IMPORTANT]
> **Local, private, no egress.** All compute is local and user-controlled. The app makes **no outbound
> network call** and transmits **no sequence data externally** — a guarantee enforced by a test that fails
> if any socket connects during a design request. The served frontend says so prominently and loads no
> third-party scripts.

| Method & path | Purpose |
|---|---|
| `GET /api/health` | Liveness, reference status, disclaimer |
| `POST /api/resolve` | Normalize any input form to a canonical variant |
| `POST /api/design` | Variant → ranked menu; `?format=json\|html\|pdf` |
| `POST /api/jobs/design` → `GET /api/jobs/{id}` | Async job submit + status/progress/result |
| `POST /api/batch` | Cohort design over a variant list; per-item summaries + provenance, failures isolated |
| `POST /api/offtarget` | Standalone population-aware off-target search — full report plus the aggregate summary (site count, worst-case, specificity) |
| `GET /api/data` · `/api/data/{name}` | Inspect the dataset registry |
| `GET /api/bench` | List the CRISPR-Bench tasks, datasets, and primary metrics |
| `GET /` | The served single-page frontend |

```bash
# One-command local deploy (reference FASTA mounted at ./data/reference.fa)
docker compose up --build          # → http://localhost:8000  ·  /docs for OpenAPI

# Or run directly
pip install "alleleforge[web]"
ALLELEFORGE_REFERENCE_FASTA=hg38.fa uvicorn alleleforge.web.api.app:app --port 8000

# Cohort design over HTTP: post a variant list, get per-item summaries + provenance
curl -s localhost:8000/api/batch -H 'content-type: application/json' \
    -d '{"variants": ["chr2:71:A>C", "VCV000012345"], "intent": "correct"}'
```

The async job worker is **in-process** (the default deployment is single-user and local), so no broker or
separate worker container is needed; a multi-user deployment can swap in a real broker behind the same
`JobManager` interface. The served vanilla-JS frontend (single-variant + cohort tabs) ships inside the
wheel and is exercised end to end by the API tests; a production Next.js + JBrowse 2 frontend can replace
it behind the same API unchanged.

---

## CRISPR-Bench: a calibration-first benchmark (Phase 14, shipping now)

The sister deliverable and a field-level contribution in its own right: a **common yardstick** for guide- and
edit-design models — versioned datasets, **frozen content-hashed splits**, a fixed **five-task contract**, a
metric battery where **calibration is required on every task**, a runner that turns any `Scorer` into a
*signed* result, and a **model-card-gated leaderboard**. It is valuable independently of the rest of
AlleleForge, and the same scorers the designer uses are graded by it.

```mermaid
flowchart LR
    DS["datasets/<br/>provenance-stamped,<br/>content-hashed"] --> SP
    SP["splits/<br/>frozen · cross-context<br/>hash-verified on read"] --> RUN
    SC["any Scorer<br/>(returns a calibrated<br/>Prediction)"] --> RUN
    RUN["runner<br/>metrics + ECE"] --> RES["signed, provenance-<br/>stamped result"]
    RES --> LB["leaderboard<br/>(model-card gated)"]
```

**The five tasks** — every chemistry AlleleForge designs for, plus off-target. Each reports its accuracy
metric **and** Expected Calibration Error, because a model that is accurate but overconfident is dangerous
for edit design:

| Task | Kind | Source corpus | Primary metric | + required |
|---|---|---|---|---|
| `cas9-efficiency` | regression | Rule Set 3, DeepHF/DeepSpCas9 | Spearman | Pearson, **ECE** |
| `cas9-outcome` | distribution | FORECasT, inDelphi, Lindel | KL ↓ | top-1, **ECE** |
| `be-outcome` | distribution | BE-Hive, BE-DICT | KL ↓ | top-1, **ECE** |
| `pe-efficiency` | regression | PRIDICT2 Library-Diverse | Spearman | Pearson, **ECE** |
| `offtarget-classification` | classification | GUIDE-seq / CHANGE-seq | AUROC | AUPRC, **ECE** |

**Frozen, content-hashed, cross-context splits.** A split is immutable once published. Each split file pins
its fold membership and two hashes — one over the **dataset content** it was cut from, one over its **own
membership** — and `load_split()` re-verifies both on read, raising `SplitIntegrityError` on any drift.
Changing the data, or the split, means minting a new *version*; you never edit a published one. Test folds
hold out a whole cell context, so the benchmark measures **generalization, not memorization** — the known
weak spot of guide models, made a headline feature instead of a footnote. `benchmark.generalization_gap`
turns that into a number: a model's primary metric on an in-context fold vs the held-out cell type,
oriented so a positive gap means worse generalization (R5; reported in the calibration study).

**Honest by construction.** Results are content-addressed (`signature`) so a published number cannot be
silently edited, and the leaderboard refuses any submission lacking a model card (name, license, citation) or
carrying a bad signature — `aforge bench leaderboard *.json` aggregates signed results into the board
(Markdown/HTML), enforcing both gates on read. The regression-task ECE is **interval-coverage calibration**
(`|empirical coverage − nominal|`), and because that is only well-defined against a single nominal level it
is computed **per `interval_level` and count-weighted** — a scorer that mixes interval levels in one batch is
scored correctly, never pooled against one prediction's level. The shipped datasets are **small synthetic fixtures** so the
whole benchmark runs in CI with no downloads; the real corpora are fetched at runtime through the same
consent-gated registry as the population data. See
[`src/alleleforge/benchmark/README.md`](src/alleleforge/benchmark/README.md).

```bash
aforge bench list                                  # the five tasks, datasets, and metrics
aforge bench run cas9-efficiency                   # score the reference baseline on the frozen split
aforge bench run pe-efficiency --out result.json   # signed, provenance-stamped result JSON
aforge bench leaderboard *.json --format html --out board.html  # model-card-gated board
```

```python
from alleleforge.benchmark import build_baseline, get_task, load_split, run_benchmark

task = get_task("offtarget-classification")
split, dataset = load_split(task.name)             # hash-verified on read
result = run_benchmark(build_baseline(task, split, dataset), task, split=split, dataset=dataset)
print(result.primary_metric, round(result.primary_value, 3), "ece", round(result.metrics["ece"], 3))
assert result.verify_signature()
```

> [!NOTE]
> The benchmark lives at `alleleforge.benchmark` (an installed subpackage) rather than the spec's sketched
> top-level `benchmark/` tree, so it ships in the wheel, is reachable from `aforge bench`, and is held to the
> same `mypy --strict` / ruff / coverage gates as the rest of the library.

**Calibration & generalization, at a glance.** Every task reports its ECE, and the cross-cell-type gap is a
first-class number. The figures below are computed on the **weight-free** splits — they verify the *machinery*
(the metric battery, the split mechanics, the generalization-gap computation), not model quality, which awaits
the real-weights integration (R1). Split-conformal recalibration restores interval coverage to its nominal
target with a finite-sample guarantee.

![Per-task ECE across the five CRISPR-Bench tasks, with the miscalibration flag threshold.](docs/assets/figures/task_ece.svg)

![Per-task cross-cell-type generalization gap, oriented so positive means worse generalization.](docs/assets/figures/generalization_gap.svg)

![Raw coverage near 19% rises to the nominal 80%/90% target after split-conformal recalibration.](docs/assets/figures/conformal_coverage.svg)

---

## Runnable examples (Phase 15)

Three notebooks walk the journey end to end. Each is **self-contained** — it builds a small synthetic
locus and runs against the weight-free stub models — so they **execute in CI on every push** (`pytest
--nbmake examples/`) and reproduce without downloading a genome or model weights. Point them at a real
hg38 reference, a gnomAD database, and trained weights via the model zoo, and the call shapes are identical.

| Notebook | What it demonstrates |
|---|---|
| [`01_clinvar_to_design`](examples/01_clinvar_to_design.ipynb) | The canonical journey: a variant → ranked **prime-editing** design across all four axes. |
| [`02_population_offtarget`](examples/02_population_offtarget.ipynb) | The **reference-bias** case (`rs114518452`): a reference-only scan is blind to a population allele that creates a de-novo PAM; the population-aware engine nominates it and reports it **ancestry-stratified**. |
| [`03_batch_vcf`](examples/03_batch_vcf.ipynb) | **Cohort-scale** design: resolve a batch of variants, design each, and reduce to one auditable summary with provenance. |

Full docs (concept guides, deployment, CLI reference, CRISPR-Bench, a
[methods-preprint outline](docs/paper/outline.md)) build with `mkdocs build --strict` in CI.

## Release & packaging (Phase 15)

The release pipeline is wired and **tag-triggered** ([`.github/workflows/release.yml`](.github/workflows/release.yml)) —
it stays inert until `v0.1.0` is tagged, then it:

| Target | Mechanism |
|---|---|
| **PyPI** | `python -m build` → `pypa/gh-action-pypi-publish` via OIDC Trusted Publishing (no stored token) |
| **Docker** | multi-arch (`linux/amd64` + `linux/arm64`) image pushed to GHCR with buildx |
| **GitHub Release** | sdist + wheel + **CycloneDX SBOM** attached, notes auto-generated |
| **SBOM** | `cyclonedx-py` over the resolved dependency closure, attached to the release |
| **Zenodo DOI** | minted on the tagged release ([`.zenodo.json`](.zenodo.json)) |
| **conda** | bioconda-style recipe ([`conda/meta.yaml`](conda/meta.yaml)) |

First public release is **v0.1.0** (three chemistries end to end with the benchmark); **v1.0.0** is reserved
for after external validation and the methods preprint. `CITATION.cff` ships for citation.

---

## Defaults cheat-sheet

Every default is overridable; these are the spec-mandated starting points.

| Topic | Default | Notes |
|---|---|---|
| Reference / coordinates | hg38, **0-based half-open** | T2T-CHM13 auto-recommended for ambiguous loci; mm39 for mouse |
| Strand | always explicit | no implicit "default strand"; spacers stored 5'→3' |
| SpCas9 PAM | `NGG` (primary), `NAG` low-stringency | NG / SpRY opt-in when no NGG is actionable |
| Off-target search | ≤ 4 mismatches, ≤ 1 DNA + ≤ 1 RNA bulge | report CFD ≥ 0.20 **or** MIT ≥ 0.10 |
| Population inclusion | MAF ≥ 0.001, all populations | de-novo PAM &amp; seed-mismatch changes always evaluated |
| Base-editing window | protospacer positions **4–8** | ABE8e (A→G), CBE4max / evoCDA1 (C→T); bystanders always reported |
| Prime editing | **PE5max + epegRNA (tevopreQ1)** | PBS 8–17 nt, RTT 7–34 nt; PE3b nicking guide when seed-disrupting |
| Uncertainty | **80%** predictive interval | deep ensemble (N=5) + isotonic calibration |
| Seed | `20240501` | threaded through every stochastic step, recorded in provenance |

---

## Project layout

```
alleleforge/
├── pyproject.toml            # hatchling build, deps, ruff/mypy/pytest config
├── SPEC.md                   # the authoritative, phase-by-phase build contract
├── rust/                     # PyO3 crate: aforge_native (BWT, k-mer, haplotype)
├── src/alleleforge/
│   ├── config.py             # typed Settings (pydantic-settings), defaults, paths
│   ├── cache.py              # R4: content-addressed cross-run disk cache (embeddings · off-target)
│   ├── _native.py            # optional Rust bridge
│   ├── types/                # Phase 1: core domain vocabulary
│   ├── genome/               # Phase 2: reference access, FM-index, liftover
│   ├── data/                 # Phase 3: registry, ClinVar, gnomAD, 1000G/HGDP, dbSNP, annotations
│   ├── variant/              # Phase 4: resolver, HGVS adapter, consequence
│   ├── offtarget/            # Phase 5: population/haplotype-aware off-target
│   ├── model_zoo/            # Phase 6: license-gated model cards + checkpoints
│   ├── scoring/              # Phase 6: embeddings, uncertainty, Scorer (this release)
│   ├── enumerate/            # Phases 7–9: SpCas9 guide · base-editor window · pegRNA enumeration
│   ├── design/               # Phases 7–10: nuclease · base · prime verticals + designer (routing · ranking) + cohort (R4 batch)
│   ├── report/               # Phase 11: oligos · report builder · JSON/TSV/Parquet · HTML · PDF
│   ├── cli/                   # Phase 12: the aforge Typer CLI (resolve · design · batch · offtarget · data · bench)
│   ├── web/                   # Phase 13: FastAPI api/ + served frontend/ (variant-first journey)
│   ├── benchmark/             # Phase 14: CRISPR-Bench — tasks · datasets · frozen splits · runner · leaderboard · calibration (R5)
│   ├── viz/                   # R5: dependency-free SVG figure renderer (reference bias · coverage · ECE · gap)
│   └── ...
├── Makefile                  # local mirror of the CI gate (make ci · reproduce · figures · native)
├── tests/                    # mirrors src/; pytest + hypothesis
├── examples/                 # Phase 15: runnable notebooks (executed in CI via nbmake)
├── scripts/                  # schema export · benchmark-fixture generator · reproduce (R0) · native_speedup · calibration_study · figures (R5)
├── conda/                    # Phase 15: bioconda-style recipe
├── docs/                     # mkdocs-material site (concepts · deployment · reference · paper · assets/figures)
└── .github/                  # workflows: ci.yml (lint·type·test·docs·examples·rust·security·reproduce) · release.yml · dependabot.yml
```

---

## Development

```bash
pip install -e ".[dev]"
ruff check src tests scripts        # lint + import order + docstrings
ruff format --check src tests scripts  # formatting
mypy --strict src/alleleforge       # strict type-check
pytest                              # tests + ≥85% coverage gate on core
pytest --nbmake examples/ --no-cov  # execute the example notebooks
cd rust && cargo test && maturin develop   # native crate
```

The library is **fully typed and ships a PEP 561 `py.typed` marker**, so `mypy`/`pyright` see its types
when you depend on it. A `Makefile` mirrors the gate so `make ci` reproduces it locally
(`make lint type test docs reproduce`; `make figures` for the docs figures, `make native` for the crate).

CI (GitHub Actions) runs lint, type-check (`mypy --strict`), tests (Python 3.11 + 3.12 on Linux &amp; macOS),
a strict docs build, notebook execution, the Rust crate (`cargo fmt` · `clippy` · `maturin build` plus a
native↔Python FM-index parity run), a **supply-chain audit** (`pip-audit` + `cargo audit`), and a
**reproducibility audit** (`scripts/reproduce.py` re-derives the canonical run from config + seed and
diffs it against a committed golden) on every push and PR. See [`.github/workflows/ci.yml`](.github/workflows/ci.yml);
releases are cut on `v*` tags by [`.github/workflows/release.yml`](.github/workflows/release.yml) and emit
a CycloneDX SBOM. [Dependabot](.github/dependabot.yml) tracks pip, cargo, and github-actions. The native
Rust crate builds locally with maturin (`cd rust && maturin develop`); the library runs in pure-Python
mode without it.

Contributions are welcome — please read [`CONTRIBUTING.md`](CONTRIBUTING.md) and the
[Contributor Covenant 2.1](CODE_OF_CONDUCT.md) code of conduct.

### Acceptance: the definition of done, as executable checks

[`tests/test_acceptance.py`](tests/test_acceptance.py) encodes the v0.1.0 release contract — the
specification's "definition of done" — as six end-to-end tests that run on every push:

| Release criterion | Proven by |
|---|---|
| A **ClinVar accession** flows end to end to a complete, provenance-stamped menu | `test_clinvar_accession_to_complete_menu` |
| The unified entry point **reaches every chemistry** (base · prime · nuclease) | `test_every_chemistry_reachable_through_one_entry_point` |
| A run is **reproducible from config + seed** (identical serialized menu) | `test_run_is_reproducible_from_seed` |
| The **reference-bias / `rs114518452`** off-target case is reproduced | `test_reference_bias_case_reproduced` |
| **Prime editing unifies all four axes** | `test_prime_unifies_all_four_axes` |
| **CRISPR-Bench publishes** the Cas9-/PE-efficiency + off-target tasks with calibration & a leaderboard | `test_crispr_bench_publishes_required_tasks` |

---

## Scope &amp; responsible use

- **Research use only.** AlleleForge produces hypotheses and rankings, not medical advice or clinical
  decisions. Every generated report repeats this.
- **Off-target predictions require experimental validation.** Computational nomination narrows the search;
  it does not replace GUIDE-seq / CHANGE-seq / amplicon confirmation.
- **No telemetry, no phone-home.** All computation runs locally or on user-controlled infrastructure.
  User sequences are never transmitted externally.
- **Honest uncertainty over false confidence.** Where models are out of distribution (e.g., prime-editing
  efficiency outside PRIDICT's HEK293T / K562 training context), AlleleForge flags it rather than hiding it.
- **Dual-use awareness.** This is a design and safety-analysis tool for legitimate therapeutic and basic
  research. It contains no wet-lab protocols or synthesis instructions.

---

## License

AlleleForge is released under the [MIT License](LICENSE) — all code, schemas, benchmark, and any first-party
model weights. It is fully open source and free to use, modify, and redistribute.

Each wrapped third-party tool or model retains its own upstream license, recorded in its model/tool card; the
registry refuses to bundle any component whose license is incompatible with redistribution and fetches it at
runtime with the user's consent instead.

## Citation

If you use AlleleForge, please cite it via [`CITATION.cff`](CITATION.cff). A Zenodo DOI is minted on the first
tagged release. The methods are written up in the draft preprint at
[`docs/paper/preprint.md`](docs/paper/preprint.md) (the posted version, with the real-data validation
numbers, follows the v1.0 release).
