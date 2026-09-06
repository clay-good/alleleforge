# Data provenance

AlleleForge's population-aware analysis depends on a small set of public
datasets. Every one is declared in the **dataset registry**
([`alleleforge.data.registry`][src]) as a typed, versioned, license-aware
descriptor. The registry is the single choke point for acquisition and enforces
two invariants:

- **No non-redistributable source is ever vendored.** A descriptor whose
  `redistributable` flag is false is fetched only into the *user's* cache at
  runtime, with explicit consent — never written into the repository or a built
  image.
- **No unverifiable artifact is fetched.** A download requires a pinned
  `sha256`; AlleleForge refuses to fetch what it cannot checksum-verify, and
  raises on a mismatch.

## Two ways to say yes

Nothing is downloaded unless you say so, in one of two forms:

| Form | Scope | Use it when |
|---|---|---|
| `consent=True` at the call | That one fetch | A script or notebook opts in for a specific artifact |
| `allow_network = true` in config (or `ALLELEFORGE_ALLOW_NETWORK=1`) | Every artifact fetch in the process | The machine has already agreed — a container build, a lab workstation |

Both are checked by the same predicate, `alleleforge.config.artifact_download_permitted`,
so the model zoo, the dataset registry and the reference-genome registry cannot drift
apart on what counts as permission.

Neither one authorizes sending your data *out*. Fetching a reference genome and
disclosing a variant to a third-party API are different acts, and the second is asked for
separately at the only place that does it — `VepRestPredictor`, which will not send a
variant to Ensembl without its own explicit consent, whatever `allow_network` says.

Access returns the cached path together with a `DatasetVersion`, which is
embedded in every result's provenance block so an analysis can be traced back to
the exact release it used.

[src]: https://github.com/clay-good/alleleforge/blob/main/src/alleleforge/data/registry.py

## Pinned datasets

| Dataset | Version | License | Citation | Used for |
|---|---|---|---|---|
| **ClinVar** | 2024-05 | Public domain (NCBI) | Landrum et al., *Nucleic Acids Res* 2018 | Variant front-end: accession → normalized variant + clinical significance (class *and* review status, carried onto the resolved variant and stated in the menu) |
| **gnomAD** | v4.1 | CC0-1.0 | Chen et al., *Nature* 2024 | Per-population allele frequencies for off-target augmentation |
| **1000 Genomes** | phase 3, high-coverage | Public (IGSR) | Byrska-Bishop et al., *Cell* 2022 | Phased common haplotypes for haplotype-aware search |
| **HGDP** | gnomAD v3.1 | CC0-1.0 | Bergström et al., *Science* 2020 | Ancestry breadth beyond 1000G super-populations |
| **dbSNP** | b156 | Public domain (NCBI) | Sherry et al., *Nucleic Acids Res* 2001 | rsID ↔ locus resolution |
| **GENCODE** | v47 | Open (GENCODE) | Frankish et al., *Nucleic Acids Res* 2023 | Gene models for transcript selection |
| **ENCODE** | 2024 | Open (ENCODE policy) | ENCODE Project Consortium, *Nature* 2012 | Chromatin tracks (DNase/ATAC/CTCF/H3K27ac) for chromatin-aware scoring |

The `sha256` of each release artifact is intentionally unset until the data
layer pins concrete files; until then auto-download stays disabled (a fetch
without a verifiable checksum is refused), while the descriptors already document
provenance for this page and the `aforge data` command.

## Population and ancestry labels

Off-target reports are **ancestry-stratified by default**, so the safety of a
design is reported per population rather than hidden behind a global average.

- **gnomAD v4.1 genetic-ancestry groups:** `afr`, `amr`, `asj`, `eas`, `fin`,
  `nfe`, `sas`.
- **1000 Genomes super-populations:** `AFR`, `AMR`, `EAS`, `EUR`, `SAS`.
- **HGDP regions:** `africa`, `america`, `central_south_asia`, `east_asia`,
  `europe`, `middle_east`, `oceania`.

The default population minor-allele-frequency inclusion threshold is
**MAF ≥ 0.001** in any queried population (overridable per call).

## Coordinate conventions on ingest

All parsers normalize to AlleleForge's internal **0-based half-open**
coordinates at the boundary:

| Source format | Native coordinates | On read |
|---|---|---|
| ClinVar VCF, gnomAD sites, dbSNP VCF | 1-based | `pos − 1` |
| GENCODE GTF | 1-based inclusive | `[start − 1, end)` |
| ENCODE bedGraph | 0-based half-open | unchanged |

The two **human** boundaries follow the same convention, and it is worth stating
plainly because the tool is uniformly BED-style while most genomics interfaces are not:

| Boundary | Meaning |
|---|---|
| `--region chrom:start-end`, `--regions-bed` | 0-based half-open. `chr7:100-200` is **100 bases** starting at offset 100 — not the 101 a genome browser would show for the same string. |
| Every locus a report prints (cut site, nick site, off-target interval) | 0-based half-open, so a printed locus can be handed straight back to `--region`. |

`--variant` and `--pop-freqs` are the exception, and say so in their own help: they
take **1-based** positions, because that is what a VCF record holds.

Every rendered report states the convention in its footer. A caller converting a
locus for display elsewhere can use `GenomicInterval.to_one_based()`.

Contig names are reconciled so an NCBI-style source (`2`, `MT`) and a UCSC-style hg38
reference (`chr2`, `chrM`) align: parsers prefix bare names to the `chr…` form (mapping the
mitochondrion to `chrM`, not `chrMT`), and every cross-source lookup compares contigs
through a canonical form (`canonical_contig`) so a naming mismatch never silently returns
nothing.

## Testing without genome-scale files

Every parser reads plain-text (optionally gzipped) input, so the test suite runs
against small synthetic fixtures and never downloads a multi-gigabyte release.
The heavier tabix/VCF backends (`pysam`, `cyvcf2`) are imported lazily on the
production path only; CI needs neither.
