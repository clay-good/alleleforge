# Bulletproof off-target nomination

## Why

Population/haplotype-aware off-target nomination is AlleleForge's genuinely
differentiated capability — the part the readiness assessment says to "promote without
caveats." That makes its correctness the whole value proposition, and three code-level
issues undercut it:

1. **First-alignment, not best-alignment, per anchor.** `_evaluate` short-circuits on the
   first in-budget alignment (`offtarget/_search.py:135-162`): an ungapped alignment at 4
   mismatches is returned even when a 1-bulge/0-mismatch alignment (higher CFD, more
   dangerous) exists at the same anchor. The reported edit counts — and therefore the CFD
   score and the safety ranking — can **under-state** a site's risk.
2. **Indel variants shift downstream coordinates.** Population and haplotype passes map
   alt-local hits to genomic coordinates 1:1 (`offtarget/population.py:84-95`,
   `offtarget/haplotype.py:93-117`). When a variant or haplotype contains an insertion or
   deletion, every hit 3' of the indel is reported at the **wrong genomic locus**, and the
   ref-vs-alt "strengthened" comparison keyed on coordinates breaks. Correct only for
   equal-length (SNV) edits today.
3. **All-or-nothing haplotype application.** A single clashing variant makes
   `_apply_haplotype` return `None` and drops the **entire** haplotype's nominations
   (`offtarget/_haplotype.py:45-52`, `haplotype.py:90-92`), discarding sites the
   non-clashing variants would have created.

A fourth, smaller issue: the FM-index path rejects non-`ACGTN` bases while the linear scan
tolerates them (`rust/src/bwt.rs:82-89` vs `_search.py:375-377`), so "which path ran"
changes behavior on dirty input — a latent native/Python divergence.

## What Changes

- Return the **edit-minimal / maximum-CFD** alignment per anchor, not the first, so a
  bulged near-perfect match is never under-scored.
- **Reindex alt-sequence hits back to true genomic coordinates** through the indel (a
  coordinate lift), so population and haplotype passes are correct for insertions and
  deletions — a capability CRISPOR and Cas-OFFinder lack.
- Apply the **non-clashing subset** of a haplotype instead of dropping it whole.
- **Unify dirty-input handling** so the linear and FM paths agree (both skip, or both
  reject) on non-`ACGTN` bases, and add a genome-scale parity case.

## Impact

- Specs: `offtarget-nomination` (MODIFIED alignment selection; ADDED indel-aware
  coordinates and partial-haplotype application), `native-kernels` (ADDED dirty-input
  parity).
- Code: `offtarget/_search.py`, `offtarget/population.py`, `offtarget/haplotype.py`,
  `offtarget/_haplotype.py`, and the corresponding Rust kernels for parity.
- Tests: indel-variant nomination at correct loci; a haplotype with one clashing and one
  PAM-creating variant still nominates the created site; best-alignment-per-anchor;
  large-genome FM/linear parity including poly-N/poly-A. This changes some nominated
  coordinates and scores, so regenerate any affected off-target goldens.
