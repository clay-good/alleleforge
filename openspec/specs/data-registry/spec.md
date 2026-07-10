# data-registry Specification

## Purpose

Be the single license-aware, consent-gated, checksum-verified choke point for every
external dataset (gnomAD, 1000G, HGDP, ClinVar, dbSNP, GENCODE, ENCODE, haplotype
panels), and provide parsers that turn each pinned release into queryable,
provenance-tagged, coordinate-normalized models.

## Requirements

### Requirement: External datasets are consent- and checksum-gated

`DatasetRegistry.resolve` SHALL raise `ConsentError` for an uncached dataset without
`consent=True`, `ChecksumError` when the descriptor's `sha256` is `None`, and
`ConsentError` when `source_url` is `None`; downloaded bytes SHALL be SHA-256 verified.
When the descriptor pins a `sha256`, `resolve` SHALL ALSO re-verify an already-cached
artifact against it on every load, so a corrupted or tampered cached dataset cannot be
served. An unregistered name SHALL raise `KeyError`.

#### Scenario: Uncached dataset without consent
- **WHEN** `resolve` is called for an uncached dataset without consent
- **THEN** it raises `ConsentError`

#### Scenario: Unpinned checksum
- **WHEN** consent is given but the descriptor's `sha256` is `None`
- **THEN** it raises `ChecksumError`

#### Scenario: Tampered cached dataset
- **WHEN** a cached dataset's bytes no longer match the pinned `sha256`
- **THEN** `resolve` raises `ChecksumError` rather than returning the stale file

### Requirement: Every dataset is a pinned, cited release

`resolve` SHALL return `(path, DatasetVersion)` so every artifact is traceable to a
pinned version, and every registry descriptor SHALL carry version, `source_url`,
license, and citation.

#### Scenario: Traceable resolution
- **WHEN** a dataset resolves successfully
- **THEN** the returned `DatasetVersion` records its version, license, and citation

### Requirement: Parsers normalize coordinates to 0-based internally

Dataset parsers SHALL convert file-native coordinates to the internal 0-based
half-open convention: gnomAD/dbSNP/ClinVar POS (1-based) → 0-based, GTF/GENCODE
(1-based inclusive) → 0-based, while haplotype-TSV and bedGraph inputs (already 0-based)
pass through unchanged.

#### Scenario: 1-based gnomAD position
- **WHEN** a gnomAD record lists a variant at 1-based position 100
- **THEN** it is stored at 0-based position 99

### Requirement: Parsers reconcile contig naming

Every dataset parser and interval query SHALL be contig-naming-independent — indexing and
looking up by the canonical contig (via `canonical_contig`) so a `chr`-named record and a
bare-named (`2`, `MT`) query reconcile, and normalizing the mitochondrion to the hg38
spelling `chrM` (not `chrMT`) when prefixing bare names — so a reference-vs-source naming
mismatch never silently returns nothing.

#### Scenario: Bare-named query finds a chr-named record
- **WHEN** a loader holds records stored as `chr2` and is queried with a bare `2` interval
- **THEN** the matching records are returned, not an empty result

#### Scenario: Mitochondrion uses the hg38 spelling
- **WHEN** a record's source contig is `MT` and bare names are prefixed
- **THEN** it is stored as `chrM`, the contig an hg38 reference is keyed by

### Requirement: Database parsers record each record's native assembly

ClinVar, dbSNP, and other assembly-bound parsers SHALL record the native assembly of each
parsed record rather than inheriting a default build silently. The recorded assembly SHALL
be available to variant resolution so a requested build can be reconciled against — not
overwritten onto — the source data.

#### Scenario: Parsed record carries its assembly
- **WHEN** a ClinVar or dbSNP release is parsed with its assembly stated (in the header or
  by the caller)
- **THEN** each resulting variant carries that assembly, not an unexamined default

#### Scenario: Assembly absent from the source
- **WHEN** the source data does not state its assembly
- **THEN** the parser records the assembly as unknown rather than assuming the default
  build, so downstream resolution can require the caller to disambiguate

### Requirement: ClinVar rows are filtered and normalized

ClinVar parsing SHALL skip reference-only/symbolic rows (`ALT` in `.`/empty) and
short (`<8`-column) rows, normalize `CLNSIG` to an ACMG class (unknown → `OTHER`,
missing → `NOT_PROVIDED`), and reconstruct the `VCV` accession as `VCV{id:09d}`.

#### Scenario: Symbolic ALT
- **WHEN** a ClinVar row has `ALT = .`
- **THEN** the row is skipped

### Requirement: Population-frequency queries support ancestry and MAF thresholds

`GnomadDB.frequencies` SHALL support per-population restriction and a `maf` inclusion
threshold, and `PopulationFrequency.max_af` with no population SHALL consider the
overall plus all population frequencies.

#### Scenario: MAF filter
- **WHEN** frequencies are requested with a `maf` threshold
- **THEN** only variants meeting the threshold are returned

### Requirement: Malformed headers and missing keys fail loudly

TSV parsers SHALL raise `ValueError` if the `#`-header line is missing before data;
`DbSnpDB` SHALL raise `ValueError` for an input variant lacking an `rsid` and `KeyError`
for an unknown rsID; `GeneModels.gene` SHALL raise `KeyError` when absent and
`ValueError` when a symbol is ambiguous.

#### Scenario: Missing header
- **WHEN** a TSV has data rows but no `#`-header line
- **THEN** the parser raises `ValueError`

#### Scenario: Ambiguous gene symbol
- **WHEN** `gene()` is called for a symbol shared by two GENCODE genes
- **THEN** it raises `ValueError`

### Requirement: Haplotype panels merge and rank by frequency

`HaplotypePanel.from_tsv` SHALL merge rows sharing `(hap_id, chrom:start-end)` into one
haplotype accumulating per-population frequencies, and `common_haplotypes` SHALL filter
by `max_freq >= min_freq`, optionally drop the reference haplotype, and sort by
descending frequency.

#### Scenario: Common haplotypes
- **WHEN** `common_haplotypes(min_freq=f)` is queried
- **THEN** only haplotypes with `max_freq >= f` are returned, sorted by descending frequency
