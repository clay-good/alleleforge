# Tasks

## 1. Best-alignment per anchor
- [x] 1.1 Change `_evaluate` to consider all in-budget alignments at an anchor (ungapped,
      DNA bulge, RNA bulge) and return the one that scores highest / is edit-minimal,
      with a deterministic tie-break.
- [x] 1.2 Test: an anchor with both a 4-mismatch ungapped and a 1-bulge/0-mismatch
      alignment reports the higher-CFD one.

## 2. Indel-aware coordinate lifting
- [x] 2.1 Build a local alt→genomic coordinate map when a variant/haplotype changes length,
      and reindex hits 3' of the indel through it.
- [x] 2.2 Make the ref-vs-alt "created/strengthened" comparison robust to the shift.
- [x] 2.3 Tests: an insertion and a deletion each nominate a created site at the correct
      genomic locus; the equal-length (SNV) path is unchanged.

## 3. Partial-haplotype application
- [x] 3.1 Apply the non-clashing subset of a haplotype's variants instead of returning
      `None` for the whole haplotype; record which variants were skipped.
- [x] 3.2 Test: a haplotype with one ref-clashing variant and one PAM-creating variant
      still nominates the created site.

## 4. Unify dirty-input handling and parity
- [x] 4.1 Make the linear scan and the FM/native path agree on non-`ACGTN` bases (both
      skip, or both reject with the same error).
- [x] 4.2 Add a genome-scale FM/linear parity test including poly-N and poly-A runs.

## 5. Reconcile goldens
- [x] 5.1 Regenerate affected off-target fixtures/goldens and the reproduce golden.
- [x] 5.2 `make ci` green; native parity job green.
