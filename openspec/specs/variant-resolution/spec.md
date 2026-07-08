# variant-resolution Specification

## Purpose

Turn any input form — ClinVar accession, dbSNP rsID, HGVS (`g./c./p.`), VCF record, raw
`chrom:pos:ref>alt` coordinates, a raw target sequence, or a `Variant` — into one
canonical, left-aligned, reference-validated `ResolvedVariant` with a working interval.
This is the variant-first entry point of the whole tool.

## Requirements

### Requirement: Any supported input form resolves canonically

`resolve` SHALL dispatch by input type and, for strings, by pattern (rsID → ClinVar →
HGVS → `chrom:pos:ref>alt`), raising `ValueError` on an unrecognized string.

#### Scenario: Unrecognized string
- **WHEN** a string matching no supported pattern is resolved
- **THEN** it raises `ValueError`

#### Scenario: Coordinate string
- **WHEN** `chrom:pos:ref>alt` is resolved (1-based)
- **THEN** it becomes a 0-based `ResolvedVariant`

### Requirement: Variants are normalized and left-aligned deterministically

`Variant.normalized` SHALL apply anchored trimming (bcftools-norm semantics), keep both
alleles at least one base, and be idempotent. When a reference is supplied, `resolve`
SHALL left-align pure indels through reference repeats and re-anchor; when omitted, it
SHALL only normalize.

#### Scenario: Indel in a homopolymer
- **WHEN** a deletion inside a homopolymer is resolved with a reference
- **THEN** it left-aligns to the repeat start

#### Scenario: Idempotence
- **WHEN** `normalized` is applied twice
- **THEN** the second application returns an equal variant

### Requirement: Reference mismatches fail closed

When a reference is supplied, an asserted `ref` disagreeing with the reference (or
over-running into N-padding) SHALL raise `ValueError` naming a reference mismatch. When
no reference is supplied, `resolve` SHALL normalize without validation.

#### Scenario: Wrong asserted ref
- **WHEN** the asserted `ref` disagrees with the reference base at that position
- **THEN** `resolve` raises `ValueError` ("reference mismatch")

#### Scenario: No reference available
- **WHEN** no reference is supplied
- **THEN** the variant is normalized but not reference-validated

### Requirement: Insertions validate their anchor before re-anchoring

For an anchored insertion, `resolve` SHALL validate the caller's asserted anchor/flanking
base against the reference **before** left-alignment re-anchors it from the reference, and
SHALL raise a reference-mismatch `ValueError` when the asserted anchor disagrees — so
left-alignment can never erase a wrong-build signal by replacing the asserted anchor with a
freshly-read reference base.

#### Scenario: Wrong-build insertion
- **WHEN** an insertion `chr1:100 A>AT` is resolved against a reference that carries `G` at
  position 100
- **THEN** resolution raises a reference-mismatch error, rather than silently re-anchoring to
  `G>GT`

#### Scenario: Correct insertion
- **WHEN** an insertion's asserted anchor matches the reference
- **THEN** it left-aligns and resolves normally

### Requirement: Source-database assembly is reconciled, not overwritten

When a variant originates from a database lookup, `resolve` SHALL NOT overwrite its build
with the requested `build` unconditionally. It SHALL raise when the requested build
disagrees with the source record's recorded native assembly, unless an explicit liftover is
performed, and provenance SHALL reflect the true source build.

#### Scenario: Mismatched database assembly
- **WHEN** a GRCh37 ClinVar or dbSNP record is resolved with `build="hg38"` and no liftover
- **THEN** resolution raises, rather than relabeling the variant as hg38

#### Scenario: Matching database assembly
- **WHEN** the requested build matches the source record's native assembly
- **THEN** the variant resolves and provenance records that assembly

### Requirement: Database-backed inputs require their database

ClinVar-accession and rsID inputs SHALL raise `ValueError` when the corresponding
database is not supplied; `c.`/`p.` HGVS SHALL raise when no transcript projector is set.

#### Scenario: rsID without dbSNP
- **WHEN** an rsID is resolved with no dbSNP database available
- **THEN** it raises `ValueError`

#### Scenario: Coding HGVS without projector
- **WHEN** a `c.` HGVS is resolved with no projector
- **THEN** it raises `ValueError`

### Requirement: A working interval and build recommendation are attached

`resolve` SHALL compute a ±`window` working interval (clamped to `[0, contig_length]`
when a reference is available) and attach a T2T build recommendation only when the
working interval overlaps an hg38-difficult region.

#### Scenario: Difficult-region variant
- **WHEN** the working interval overlaps an hg38-difficult region
- **THEN** `reference_recommendation` is set on the result

### Requirement: VCF ingestion splits and filters alleles

`iter_vcf` SHALL split multi-allelic rows into one record per concrete ACGTN ALT, skip
symbolic/`*`/non-ACGTN alleles, and by default yield only `PASS`/`.` records; it SHALL
raise `RuntimeError` if a path is given without `cyvcf2` available.

#### Scenario: Multi-allelic row
- **WHEN** a VCF row has `ALT = G,T`
- **THEN** two records are yielded, one per ALT

#### Scenario: Symbolic allele
- **WHEN** a VCF row has `ALT = <DEL>` or `*`
- **THEN** that allele is skipped

### Requirement: Genomic HGVS covers the common edit classes

`parse_genomic_hgvs` SHALL support substitution, del, ins, dup, and delins, raising
`ValueError` on unsupported or non-`g.` expressions and requiring inserted/replacement
bases for ins/delins; unstated deleted/duplicated bases SHALL be filled from a supplied
`ref_lookup`, raising `ValueError` if none is given.

#### Scenario: Unsupported expression
- **WHEN** a non-`g.` or unsupported HGVS expression is parsed
- **THEN** it raises `ValueError`

### Requirement: Effect prediction never fails resolution

`StaticEffectPredictor` SHALL never fail resolution, defaulting unknown variants to
`OTHER`/`MODIFIER`; a live VEP predictor SHALL cache by `(variant, assembly,
transcript)` and prefer MANE-select, then canonical, then the first transcript.

#### Scenario: Unknown variant effect
- **WHEN** the static predictor cannot classify a variant
- **THEN** it returns `OTHER`/`MODIFIER` rather than raising
