## MODIFIED Requirements

### Requirement: Enumeration places the nick 5' of the edit within reach

For each candidate PAM the nick SHALL sit 3 bp 5' of the PAM and the edit SHALL lie 3' of
the nick; the PBS SHALL be enumerated over its length range (skipping lengths that run off
the window), and the RTT SHALL encode the edited allele plus at least 5 nt 3' homology and
not run past the template. The RT template SHALL be **variable-length** — 5' homology from
the nick to the edit, then the whole desired allele, then the 3' homology — so a
substitution, MNV, insertion, deletion, or delins is templated by the same path, a deleted
span consuming no template length. Every synthesized span (spacer, PBS, and RTT) SHALL be
concrete A/C/G/T; a pegRNA whose RTT window covers a reference `N` (assembly gap) SHALL be
skipped, consistent with the cas9/base-editor enumerators. Results SHALL be
deterministically sorted.

#### Scenario: No reachable nick
- **WHEN** no PAM places a nick 5' of the edit within RT reach
- **THEN** enumeration returns empty

#### Scenario: RTT spans an assembly gap
- **WHEN** a pegRNA's RT template window reaches a reference `N` (an assembly gap)
- **THEN** that pegRNA is skipped (its RTT would be an unsynthesizable oligo templating an
  ambiguous base into the genome), while shorter RTTs that stop before the gap still resolve

#### Scenario: Multi-base edit
- **WHEN** an insertion, deletion, MNV, or delins within the supported size is enumerated
- **THEN** pegRNAs are emitted on both strands, and each one's reverse-transcribed product
  reconstructs exactly the intended edited genome at the locus its PBS anneals to

#### Scenario: Deleted span costs no template
- **WHEN** a deletion is templated
- **THEN** the RTT length is independent of the deleted span's length (it carries only the
  5' and 3' homology), so a large deletion is templatable inside `RTT_RANGE`

#### Scenario: Deterministic order
- **WHEN** multiple pegRNAs are enumerated
- **THEN** they are sorted by nick site, then PBS length, then RTT length

### Requirement: Enumeration coverage is stated honestly

Routing SHALL advertise prime editing only for edit classes that enumeration can produce (a
feasibility check), and SHALL state a specific reason when it declines an edit it cannot
enumerate — not a generic "no actionable candidate" note. The supported edit classes SHALL
be documented. Two bounds SHALL be enforced identically by routing and enumeration: the
reference span an edit replaces SHALL be at most `PRIME_MAX_EDIT`, and the allele the RT
template must **write** (the desired allele, which depends on the intent) SHALL be at most
`PRIME_MAX_TEMPLATED_EDIT` — the `RTT_RANGE` ceiling less the minimum 3' homology.

#### Scenario: Routed but unenumerable edit
- **WHEN** an edit routes to prime but no pegRNA can be enumerated for its class
- **THEN** the menu records an explicit "eligible but no actionable candidate" note

#### Scenario: Small indel
- **WHEN** an insertion, deletion, or delins within both bounds is requested
- **THEN** routing admits prime and enumeration produces valid pegRNAs

#### Scenario: Allele too long to template
- **WHEN** the desired allele is longer than `PRIME_MAX_TEMPLATED_EDIT`
- **THEN** routing declines prime and enumeration returns empty — never a truncated RT
  template — while the opposite intent on the same variant, which writes a short allele,
  remains eligible

#### Scenario: No-op edit
- **WHEN** the start allele and the desired allele are identical
- **THEN** enumeration returns empty

## ADDED Requirements

### Requirement: Placements are reference footprints, never loci of convenience

Enumeration runs over the genome the target actually carries (the reference window with the
start allele substituted in), whose coordinates drift from the reference past a
length-changing edit. Every emitted placement and nick site SHALL be expressed in reference
coordinates as the footprint the reagent's bases derive from: exact for a span that does not
cross the edit, wider for one spanning a deletion, narrower for one spanning an insertion. A
protospacer lying wholly inside carried bases the reference does not contain has no
reference locus and SHALL be reported without a placement (pegRNA) or dropped (nicking
guide), rather than assigned a locus it does not occupy.

#### Scenario: Protospacer 5' of the edit
- **WHEN** a pegRNA's protospacer does not cross the edit
- **THEN** fetching its placement from the reference returns the protospacer verbatim

#### Scenario: Protospacer spanning a corrected deletion
- **WHEN** a protospacer spans an edit whose carried allele is shorter than the reference
  span it replaces
- **THEN** its placement is wider than the protospacer by exactly the missing bases

#### Scenario: Nicking guide with no reference locus
- **WHEN** a candidate nicking-guide protospacer lies wholly inside carried inserted bases
- **THEN** it is not emitted, and no emitted nicking guide has a zero-width placement

### Requirement: PE3b classification survives a length-changing edit

A nicking guide SHALL be classified PE3b only when the edit genuinely disrupts its
PAM-proximal seed, judged by comparing the seed window in the start and edited genomes, and
only where the two genomes share their indexing (the protospacer's PAM-proximal boundary at
or 5' of the edit). A PE3b guide's spacer SHALL be templated from the edited genome; any
other nicking guide's from the start genome.

#### Scenario: Indel in the ngRNA seed
- **WHEN** an insertion or deletion falls inside a candidate ngRNA's PAM-proximal seed
- **THEN** the guide is classified PE3b and its spacer matches the edited strand

#### Scenario: Edit past the shared indexing
- **WHEN** a candidate ngRNA's protospacer begins 3' of the edit, where a length-changing
  edit has shifted the two genomes apart
- **THEN** it is not classified PE3b and its spacer is templated from the start genome
