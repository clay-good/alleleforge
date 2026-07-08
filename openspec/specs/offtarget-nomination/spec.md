# offtarget-nomination Specification

## Purpose

Enumerate every PAM-anchored genomic site a guide could cut within a mismatch/bulge
budget — across the reference and the sequence variation (population, haplotype, patient)
that a reference-only scan is blind to. This population/haplotype awareness is the
project's key differentiator: a minor allele can create a de novo PAM a reference-only
tool misses.

## Requirements

### Requirement: Both strands are scanned within a shared edit budget

The system SHALL scan both strands of each requested region for PAM-anchored protospacer
windows within a shared `(mismatches, dna_bulges, rna_bulges)` budget (defaults 4, 1, 1),
returning plus-strand 0-based half-open coordinates and the strand the guide reads on.

#### Scenario: Exact reference match
- **WHEN** a spacer matches a reference protospacer followed by a valid PAM
- **THEN** one reference site is nominated at the exact coordinates with top score

### Requirement: Single-bulge alignment within budget

At each PAM anchor the system SHALL consider every in-budget alignment (ungapped, a
single DNA bulge, a single RNA bulge) and SHALL report the alignment that maximizes the
specificity score (edit-minimal), with a deterministic tie-break — never merely the first
in-budget alignment found. A site is still never given both bulge types at once.

#### Scenario: Best alignment wins at an anchor
- **WHEN** an anchor admits both a 4-mismatch ungapped alignment and a 1-bulge,
  0-mismatch alignment
- **THEN** the higher-scoring (edit-minimal) alignment is reported, so the site's risk is
  not under-stated

#### Scenario: Bulge only when budgeted
- **WHEN** the DNA-bulge budget is zero
- **THEN** no site is nominated that requires a DNA bulge

### Requirement: Indel variants are placed at correct genomic coordinates

When a population, haplotype, or patient variant changes the length of the local window
(an insertion or deletion), nominated hits 3' of the indel SHALL be reindexed back to
their true genomic coordinates through a local coordinate lift, and the ref-vs-alt
created/strengthened comparison SHALL remain correct across the shift.

#### Scenario: Deletion-derived hit
- **WHEN** a variant deletes bases and a downstream created site is nominated on the
  alternate allele
- **THEN** the site is reported at its correct genomic locus, not shifted by the deletion
  length

### Requirement: A haplotype's non-clashing variants are still applied

When one variant in a haplotype clashes with the reference, the system SHALL apply the
remaining non-clashing variants rather than discarding the whole haplotype, and SHALL
record which variants were skipped.

#### Scenario: One clashing variant
- **WHEN** a haplotype carries one ref-clashing variant and one PAM-creating variant
- **THEN** the created site is still nominated, and the skipped variant is recorded

### Requirement: N-containing and non-PAM windows are never nominated

The system SHALL anchor only on windows whose PAM matches the IUPAC-expanded pattern and
SHALL never nominate a site whose protospacer or PAM window contains an `N`. The primary
PAM SHALL be broadened to its low-stringency form for the scan (SpCas9 `NGG` → `NRG`),
with scoring down-weighting the weaker PAM later.

#### Scenario: N in the window
- **WHEN** an `N` sits inside a protospacer window
- **THEN** no site is nominated there

### Requirement: The seed prefilter returns the exact brute-force result

The k-mer seed prefilter SHALL skip anchors that provably contain no in-budget hit and
SHALL return exactly the unseeded brute-force result; the FM-index seed-and-extend used
for genome-scale regions SHALL return byte-identical hits to the linear scan.

#### Scenario: Seed/brute-force parity
- **WHEN** the same region is scanned with and without the seed prefilter
- **THEN** the nominated site sets are identical

### Requirement: Population augmentation nominates created or strengthened sites

Population augmentation SHALL re-scan a window around each gnomAD variant on its
alternate allele and nominate hits the variant **creates or strengthens** that overlap
the variant locus, annotated with the causal allele, carrying populations above the MAF
threshold, and per-ancestry frequency. An alt hit "strengthens" a reference hit at the
same placement when it is more dangerous by **either** measure: a strictly higher
specificity score (CFD) — so a variant that upgrades a weak PAM (e.g. `NAG`→`NGG`) at an
unchanged edit count is nominated — **or** strictly fewer edits, which catches a mismatch
or bulge the variant removes that the bulge-blind CFD score alone would not reflect. The
gate SHALL NOT rely on the edit count alone, which would drop an equal-edit PAM upgrade.

#### Scenario: De novo PAM from a minor allele
- **WHEN** the reference protospacer is followed by a non-PAM but a gnomAD variant
  creates a valid PAM
- **THEN** reference-only nomination returns zero sites and population-aware nomination
  returns one site annotated with the causal allele and its ancestry frequencies

#### Scenario: A variant upgrades a weak PAM without changing the edit count
- **WHEN** a minor allele changes a low-stringency PAM (`NAG`) into a canonical PAM
  (`NGG`) while the protospacer edit count is unchanged, raising the site's CFD
- **THEN** the strengthened site is nominated and attributed to the causal allele, rather
  than discarded because its edit count did not fall

#### Scenario: A downgraded PAM is not nominated
- **WHEN** a minor allele weakens a canonical PAM (`NGG`→`NAG`) at an unchanged edit count,
  lowering the site's CFD
- **THEN** no site is nominated — a weakening is not a strengthening

### Requirement: Haplotype and patient passes preserve co-inherited context

Haplotype-aware evaluation SHALL materialize each common haplotype's full variant set
onto the reference window, nominate created/strengthened hits restricted to haplotypes
above `min_freq` in the queried population, and tag origin with all co-inherited alleles.
The patient-VCF pass SHALL apply the same created/strengthened logic tagged as patient.

#### Scenario: Co-inherited variants
- **WHEN** a haplotype carries one variant creating the PAM and another in the protospacer
- **THEN** both alleles are recorded on a single site

#### Scenario: Below-frequency population excluded
- **WHEN** a population on a haplotype is below `min_freq`
- **THEN** it appears in neither the populations nor the ancestry burden

### Requirement: Nomination is deduplicated, sorted, and deterministic

The system SHALL de-duplicate by locus keeping the highest score, return sites sorted by
descending score, and emit ancestry maps in sorted order with alphabetical worst-ancestry
tie-breaks, so output is byte-stable across runs.

#### Scenario: Duplicate loci
- **WHEN** the same locus is nominated by two passes
- **THEN** one site is kept with the higher score

### Requirement: Variants whose asserted ref disagrees are skipped safely

When a population, haplotype, or patient variant's asserted reference base disagrees with
the build, the variant SHALL be skipped rather than mis-applied.

#### Scenario: Ref mismatch
- **WHEN** a gnomAD variant's ref base does not match the reference
- **THEN** it is skipped and no site is derived from it
