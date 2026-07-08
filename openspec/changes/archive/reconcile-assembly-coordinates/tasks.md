# Tasks

## 1. Contig-naming reconciliation — DONE

- [x] Add a contig-naming-style field to `BuildDescriptor` (e.g. `ensembl` vs `ucsc`) for
  every built-in build.
  (`BuildDescriptor.naming_style` defaults to `ensembl`; T2T-CHM13v2 declares `ucsc`.)
- [x] Have `ReferenceGenome` expose its naming style and reconcile a fetch: alias
  `chr17`↔`17` transparently, or raise an explicit "contig-naming mismatch (chr-prefix)"
  error distinct from a base-level reference mismatch.
  (`ReferenceGenome.naming_style` property + `_resolve_contig`, used by `fetch_result` and
  `contig_length`; `_contig_aliases` covers `chr`↔bare and the `chrM`/`MT`/`M` spellings.
  `ContigNamingError` subclasses `KeyError` so existing handlers still catch it while the
  message names the naming mismatch, kept distinct from a plain unknown-contig `KeyError`.)
- [x] Make `flag_ambiguous_regions` / `overlaps` naming-style aware so the hg38-difficult
  T2T recommendation fires regardless of `chr` prefix.
  (`GenomicInterval.overlaps` now compares contigs via `canonical_contig`, so the chr-named
  difficult-region table matches an Ensembl-named query and vice versa.)
- [x] Test: a `chr17` ClinVar lookup against an Ensembl-named `hg38` reference resolves (or
  errors clearly); an ambiguous region flags on both naming styles.
  (`test_fetch_aliases_chr_query_against_ensembl_reference`,
  `test_fetch_aliases_bare_query_against_ucsc_reference`,
  `test_contig_naming_mismatch_is_distinct_from_unknown`, `test_naming_style_detected`,
  `test_flag_fires_on_either_naming_style`.)

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

## 4. Source-database assembly reconciliation — DONE

- [x] Record each ClinVar/dbSNP record's native assembly at parse time (`clinvar.py`,
  `dbsnp.py`, `types/variant.py`).
  (`Variant.source_assembly` (default `None` = unknown); ClinVar sniffs the assembly from
  its VCF header (`_sniff_assembly`) or takes an explicit `assembly=`; dbSNP takes
  `assembly=` since its TSV has no header assembly.)
- [x] In `resolve`, raise when the requested `build` disagrees with a source record's
  assembly, unless an explicit liftover is performed; propagate the true source build into
  provenance and VEP assembly selection.
  (`resolve` compares `variant.source_assembly` to the requested `build` via
  `assembly_matches` before stamping the build, and raises on a disagreement. Because it
  now stamps the build only when they agree, `effect._assembly_of(variant.build)` and
  provenance already carry the true source build — no further change needed there.)
- [x] Test: a GRCh37 database queried with `build="hg38"` raises instead of relabeling.
  (`test_resolve_raises_on_source_assembly_mismatch`,
  `test_resolve_ok_when_source_assembly_matches`, plus parser tests
  `test_from_vcf_sniffs_native_assembly_from_header`,
  `test_from_vcf_assembly_unknown_when_header_silent`,
  `test_from_tsv_records_native_assembly`, `test_from_tsv_assembly_unknown_by_default`.)

## Status

All parts are **shipped**. Parts 2 (insertion-anchor validation) and 3 (liftover
length/strand fail-closed) landed earlier; part 1 (contig-naming reconciliation across
`reference.py` / `sequence.py` `overlaps` / `coordinates.py`) and part 4 (source-database
native-assembly recording across `clinvar.py` / `dbsnp.py` / `types/variant.py` / resolver)
complete the change. Ready to archive.
