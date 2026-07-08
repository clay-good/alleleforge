# Tasks

## 1. Contig-naming reconciliation

- [ ] Add a contig-naming-style field to `BuildDescriptor` (e.g. `ensembl` vs `ucsc`) for
  every built-in build.
- [ ] Have `ReferenceGenome` expose its naming style and reconcile a fetch: alias
  `chr17`↔`17` transparently, or raise an explicit "contig-naming mismatch (chr-prefix)"
  error distinct from a base-level reference mismatch.
- [ ] Make `flag_ambiguous_regions` / `overlaps` naming-style aware so the hg38-difficult
  T2T recommendation fires regardless of `chr` prefix.
- [ ] Test: a `chr17` ClinVar lookup against an Ensembl-named `hg38` reference resolves (or
  errors clearly); an ambiguous region flags on both naming styles.

## 2. Insertion-anchor validation — DONE

- [x] In `variant/resolver.py`, validate the caller's asserted anchor/flanking base against
  the reference before re-anchoring an insertion in `_left_align`.
- [x] Raise a reference-mismatch `ValueError` when the asserted anchor disagrees.
- [x] Test: `chr1:100 A>AT` where the reference has `G` at the locus raises, rather than
  silently relocating to `G>GT`.

## 3. Liftover length/strand fail-closed — DONE

- [x] In `Liftover.lift_interval`, return `None` when the lifted span length differs from
  the source length beyond a declared tolerance, or the two endpoints map to different
  strands.
- [x] Test: an interval spanning a chain indel comes back `None`; an interval straddling an
  inversion boundary comes back `None`.

## 4. Source-database assembly reconciliation

- [ ] Record each ClinVar/dbSNP record's native assembly at parse time (`clinvar.py`,
  `dbsnp.py`, `types/variant.py`).
- [ ] In `resolve`, raise when the requested `build` disagrees with a source record's
  assembly, unless an explicit liftover is performed; propagate the true source build into
  provenance and VEP assembly selection.
- [ ] Test: a GRCh37 database queried with `build="hg38"` raises instead of relabeling.

## Status

Parts 2 (insertion-anchor validation) and 3 (liftover length/strand fail-closed) are
**shipped**. Parts 1 (contig-naming reconciliation across `reference.py` / `sequence.py`
`overlaps` / `coordinates.py`) and 4 (source-database native-assembly recording across
`clinvar.py` / `dbsnp.py` / `types/variant.py` / `effect.py`) remain open — each spans the
data/effect layer and is deferred to its own focused increment.
