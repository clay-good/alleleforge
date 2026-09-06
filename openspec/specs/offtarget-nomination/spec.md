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

#### Scenario: Zero threshold with an uncarried requested population
- **WHEN** the search runs at `min_freq <= 0` (e.g. `--maf 0`) and the requested populations include one
  the haplotype records no frequency for
- **THEN** the uncarried population is excluded from the carrying set (a population with no known frequency
  does not carry the haplotype) and the search completes — it does not crash by indexing an absent frequency

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

### Requirement: The report states every budget and cut-off that narrowed it

A site count is only interpretable alongside the settings that produced it: the same guide
yields two sites at a 0.20 CFD cut-off and fifteen at 0.05, and a zero-bulge scan cannot
find the bulged hits a one-bulge scan reports. The system SHALL record, on the off-target
report itself, the mismatch budget, the DNA and RNA bulge budgets, and the CFD and MIT
reporting thresholds actually used — not only in the run's provenance — so a report can be
read, and compared with another, on its own.

#### Scenario: Non-default budgets and thresholds
- **WHEN** a search runs with `mismatches=2, dna_bulges=0, rna_bulges=0, cfd_threshold=0.05, mit_threshold=0.01`
- **THEN** the report carries exactly those five values, so its site count is not mistaken for
  a count obtained under the defaults

### Requirement: Every rendered off-target result states its search settings

Recording the budgets and cut-offs on the report is not sufficient — the reader of a
rendered artifact never sees the model. Every surface that displays a nominated-site count
or a specificity score SHALL also display the settings that count is conditional on.

#### Scenario: A rendered report shows the search
- **WHEN** an HTML page, a PDF leave-behind, or the CLI's human output shows a site count
- **THEN** it also shows the mismatch budget, the DNA and RNA bulge budgets, and the CFD and
  MIT reporting cut-offs, in characters the target medium can actually render

### Requirement: The guide is never its own off-target, however aligned

The reference always contains the guide's own protospacer, so a scan nominates it as a
perfect match. When the caller supplies the on-target placement, that site SHALL be
excluded however the aligner reaches it — including a **bulged** alignment to the same
locus, which lands at an interval differing from the placement by the bulge and scores
1.0 with zero mismatches. Counting it pegs the worst-case score at 1.0 and halves the
specificity of a spotless guide, which is the failure the exclusion exists to prevent.

A hit at any **other** locus SHALL be kept, including one abutting the on-target and one
that is itself bulged: the exclusion covers the placement grown by the hit's own bulge
budget and no more.

#### Scenario: The guide aligned to itself through a bulge
- **WHEN** the search allows bulges and nominates the guide's own locus at an interval
  one base short of the placement
- **THEN** it is excluded, and the report carries no perfect-scoring site

#### Scenario: A bulged off-target elsewhere
- **WHEN** a bulged hit lies outside the placement grown by its bulge budget
- **THEN** it is reported

### Requirement: A nominated site names the PAM that anchored it

The engine admits a low-stringency PAM alongside the canonical one, and with bulges
allowed the same span of genome is reachable from two adjacent PAMs. A site's locus,
mismatch count and score therefore do not determine what it is: a canonical and a relaxed
site look identical, and two overlapping registers are indistinguishable from one site
reported twice. Every nominated site SHALL record the concrete PAM read at it, and every
render of a site table SHALL show it.

Overlapping registers SHALL NOT be merged and no aggregate SHALL be adjusted for them.
Treating two registers as one site is a convention the project does not have; recording
the PAM lets the reader decide.

#### Scenario: Two overlapping registers
- **WHEN** bulges allow the same span to be reached from two adjacent PAMs
- **THEN** both sites are reported, each naming its own PAM

### Requirement: A scan reports how much of the region was searchable

A window containing an assembly gap or an IUPAC ambiguity code cannot be scanned, so the
reference itself — not only the caller's parameters — narrows what a search examined. A
report SHALL record the bases in the requested region(s) and how many were unambiguous
A/C/G/T, and SHALL state the searchable fraction alongside its settings when it is
materially below the whole. A fully-resolved region SHALL produce no such statement.

#### Scenario: A region that is mostly assembly gap
- **WHEN** a search covers a region dominated by `N`
- **THEN** the report states the fraction that was searchable, so a low site count is not
  read as a clean scan

#### Scenario: Fully-resolved sequence
- **WHEN** every base in the region is unambiguous
- **THEN** no searchable-fraction caveat is added

### Requirement: A supplied population source that contributes nothing is reported

Any safety source — a frequency file, a haplotype panel, a patient VCF — can be present
and cover none of the searched region: a per-chromosome download, a region subset, a
panel for another locus — and the resulting report is
indistinguishable from a reference-only scan, including the empty ancestry breakdown. The
system SHALL keep three states distinct: no source supplied, a source supplied that
contributed no variants here, and a source that contributed some; and SHALL explain the
empty breakdown in the second case.

The missing-source case is already warned about. The supplied-and-inert case is the more
dangerous one, because nothing is absent to prompt a second look.

#### Scenario: A source covering another locus
- **WHEN** any safety source is supplied whose entries all fall outside the searched region
- **THEN** the report says the source contributed nothing here and that the scan is
  effectively reference-only

#### Scenario: A frequency file that covers the region
- **WHEN** the source contributes variants
- **THEN** no such statement is made

### Requirement: A requested ancestry with no data behind it is named

Ancestries are requested as a list, and a list can be half-applied: a source with no
column for one of them drops it silently while provenance records it as considered. An
ancestry absent from the breakdown then reads as "no risk found there" when it means
"nobody looked" — the failure the population-aware search exists to prevent, in the
populations least likely to be covered and most likely to be named explicitly.

The system SHALL record which requested ancestries no supplied source carries data for,
checked across every source, and SHALL name them beside the result. It SHALL stay silent
when no source was supplied at all, since that case is warned about separately.

#### Scenario: An ancestry the source has no column for
- **WHEN** stratification is requested by an ancestry no supplied source carries
- **THEN** the report names it and says its absence from the breakdown means no data

#### Scenario: Every requested ancestry backed
- **WHEN** each requested ancestry is carried by some supplied source
- **THEN** nothing is said

### Requirement: A search that examined no sequence says so

With no sequence to scan — a truncated reference, a contig header with no bases, a scope
resolving to nothing — the report is "0 sites, worst score 0.000, specificity 1.000".
Every number is correct and the conclusion is the opposite of the truth, and the
searchable-fraction statement cannot help because there are no requested bases to take a
fraction of. A search over zero bases SHALL state that plainly beside its numbers.

#### Scenario: A truncated reference
- **WHEN** the reference holds a contig with no sequence
- **THEN** the report says no sequence was searched, rather than presenting a clean result

### Requirement: A high-scoring off-target raises a caveat

A candidate whose off-target search nominated a site at or above the triage band SHALL
carry a caveat naming the score, on every chemistry. The ranking already consumes the
score — the safety objective falls toward zero — but ranking is a comparison, so the
sole candidate for a variant is still recommended, and a reader scanning for hazards
sees only the caveats block.

#### Scenario: A perfect-match site elsewhere in the genome
- **WHEN** a nominated off-target scores at or above the band
- **THEN** the candidate carries `offtarget-high:<score>` and the report renders it as
  a caveat, whichever chemistry produced the guide

### Requirement: A non-finite threshold is refused, not reinterpreted

The fractions that govern a search — `maf`, `cfd_threshold`, `mit_threshold` — SHALL be
finite. A range check spelled as a pair of comparisons admits `NaN`, which then compares
False against every score it meets; what that means is decided by the direction of the
consumer's test rather than by anything the caller asked for. The site filter is a *skip*
test, so `NaN` reports every site while the report names a cutoff it is not applying. The
population filter is an *include* test, so `NaN` admits no record and the report shows no
population off-targets at all. The refusal SHALL name the offending parameter, and SHALL
happen before any sequence is scanned, at every entry point that accepts the fraction.

#### Scenario: A NaN minimum allele frequency
- **WHEN** a caller passes `maf=nan` to a search or to population nomination
- **THEN** it raises rather than reporting a search with no population off-targets

### Requirement: A search states the extent it covered

The one-line search description SHALL state how much sequence was examined, whether or
not that extent was fully resolvable. Every number the report carries is conditional on
the scope, and scoping to a panel is the ordinary way a run is made practical, so two
reports that searched different extents SHALL NOT describe themselves identically —
otherwise the narrower search, which nominates fewer sites, reads as the safer guide.
Where the extent was never recorded, the description SHALL say so rather than report
zero, since a stated zero invites a comparison that cannot be made.

#### Scenario: A panel scan beside a genome-wide scan
- **WHEN** the same guide is searched over one contig and then over the whole reference
- **THEN** the two descriptions differ, each naming the number of bases it covered
