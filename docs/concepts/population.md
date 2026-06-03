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
AlleleForge reproduces this reference-bias case as an integration test and a documented example as
the off-target engine lands (Phase 5).
