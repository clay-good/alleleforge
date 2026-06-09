# Population-aware safety

Reference-genome-only off-target analysis has a known, consequential blind spot: a minor allele
present in a population but absent from the reference can create a *de novo* PAM or alter a seed
mismatch, producing a high-activity off-target that a reference-only scan never sees. Because allele
frequencies differ by ancestry, that blind spot is not evenly distributed — it concentrates risk in
the populations a reference-centric pipeline under-represents.

## Ancestry stratification by default

AlleleForge searches population variation (gnomAD / 1000G / HGDP) by default and reports off-target
risk **stratified by ancestry**. Every nominated
[`OffTargetSite`][alleleforge.types.offtarget.OffTargetSite] records where it came from — the
reference, a population variant (which allele, which populations, at what frequency), or a supplied
patient VCF — so a result can be audited rather than trusted blindly.

The report's [`worst_ancestry`][alleleforge.types.offtarget.OffTargetReport.worst_ancestry] surfaces
the most-affected ancestry rather than an average, so a design that is safe on average but dangerous
in one population is correctly flagged instead of hidden behind a single global number.

## The motivating case

The canonical cautionary tale is the BCL11A enhancer site `rs114518452` (Cancellieri & Pinello,
*Nature Genetics*, 2023): a population variant creates a de-novo NGG PAM yielding a high-CFD
off-target that reference-only analysis misses, with frequency concentrated in specific ancestries.
AlleleForge reproduces this reference-bias case as an integration test
(`tests/offtarget/test_reference_bias.py`): a reference-only scan returns **zero** sites, while the
population-aware scan nominates the high-CFD off-target, ancestry-stratified, with the causal allele
and its African-ancestry-enriched frequency recorded.

## How the engine works

[`search`][alleleforge.offtarget.engine.search] runs five stages and returns one
ancestry-stratified report:

1. **Reference** — PAM-anchored, mismatch- and bulge-tolerant search over both strands (the Rust
   FM-index seed-and-extend kernel; a correct linear-scan fallback until that crate is built).
2. **Population augmentation** — for each gnomAD variant in range, re-scan the neighborhood on the
   *alternate* allele and keep any hit the variant **creates or strengthens** versus the reference.
3. **Haplotype-aware** — walk the common 1000G/HGDP haplotypes, applying each haplotype's full
   variant set, so off-targets that need a *combination* of co-inherited variants are found.
4. **Patient VCF** — optionally personalize the search to one genome.
5. **Score & aggregate** — CFD and MIT, threshold (CFD ≥ 0.20 **or** MIT ≥ 0.10), de-duplicate by
   placement keeping the strongest, sort, and stratify by ancestry.

Every threshold is a parameter; the defaults are ≤ 4 mismatches, ≤ 1 DNA + ≤ 1 RNA bulge, and
MAF ≥ 0.001 in any queried population.

## Scoring

Two published single-guide specificity scores are implemented behind one swappable
[`OffTargetScorer`][alleleforge.offtarget.scoring.OffTargetScorer] protocol:

- **MIT / Hsu** (Hsu et al., *Nat Biotechnol* 2013) — exact, from the published 20-position weight
  table.
- **CFD** (Doench et al., *Nat Biotechnol* 2016) — `∏ w(position, mismatch) · w(PAM)`. The PAM
  dinucleotide weights are the published CFD values; the per-position mismatch weights default to a
  transparent monotonic seed-tolerance model and accept the exact 400-value Doench matrix via
  injection, so the published table drops in without code changes.
- A **Cas12a CFD analog** with the seed at the PAM-proximal 5' end and a `TTTV` PAM model.

Those score one site. The report rolls them into an **aggregate genome-wide specificity score**,
[`specificity_score`][alleleforge.types.offtarget.OffTargetReport.specificity_score] — the CFD-scale
analog of the Hsu 2013 / MIT guide score `100/(100+Σ)`, i.e. `1/(1 + Σ site scores)` ∈ (0, 1]. It is
**1.0** for a guide with no off-targets and decreasing as the total off-target burden grows, and unlike
[`worst_score`][alleleforge.types.offtarget.OffTargetReport.worst_score] it distinguishes two guides
with the same worst site but a different *number* of off-targets.
