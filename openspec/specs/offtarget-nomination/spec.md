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

At each PAM anchor the system SHALL try ungapped alignment first, then (if budgeted) a
single DNA bulge, then a single RNA bulge, returning an in-budget alignment; a site is
never given both bulge types at once.

#### Scenario: Bulge only when budgeted
- **WHEN** the DNA-bulge budget is zero
- **THEN** no site is nominated that requires a DNA bulge

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
alternate allele and nominate only hits the variant creates or strengthens (fewer edits
than any reference hit at the same placement) that overlap the variant locus, annotated
with the causal allele, carrying populations above the MAF threshold, and per-ancestry
frequency.

#### Scenario: De novo PAM from a minor allele
- **WHEN** the reference protospacer is followed by a non-PAM but a gnomAD variant
  creates a valid PAM
- **THEN** reference-only nomination returns zero sites and population-aware nomination
  returns one site annotated with the causal allele and its ancestry frequencies

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
