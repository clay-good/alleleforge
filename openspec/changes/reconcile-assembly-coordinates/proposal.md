# Reconcile assembly and contig conventions

## Why

Coordinate-system and assembly mismatches are the classic source of silent scientific
error in genomics tooling, and four such holes remain in the input layer everything else
depends on:

1. **Contig naming is inconsistent end to end.** The only genomes AlleleForge can fetch are
   Ensembl-named FASTAs — `hg38` downloads `Homo_sapiens.GRCh38.dna.primary_assembly.fa.gz`
   (contigs `1, 2, … X, MT`) at `genome/reference.py:90` — but the RefSeq/HGVS resolver
   (`variant/resolver.py:38-43`), the ClinVar/dbSNP parsers (`clinvar.py:121,202`,
   `dbsnp.py:55`), and the hg38-difficult-region table (`coordinates.py:117-123`) all use
   UCSC `chr`-prefixed names. So `from_build("hg38")` + a ClinVar variant on `chr17` hits
   `fetch(chrom="chr17")` → `KeyError` (`reference.py:288`), or worse: `_validate_ref` fires
   a misleading "wrong build?" mismatch when only the name differs, and
   `flag_ambiguous_regions` silently never fires on Ensembl-named coordinates (`overlaps`
   short-circuits on unequal contig, `sequence.py:223`) — suppressing the T2T recommendation
   for hard loci. There is no single boundary that reconciles the two conventions.
2. **Insertion left-alignment erases the wrong-build signal.** For an insertion,
   `_left_align` strips the user's asserted anchor base and re-reads it from the reference
   before validating (`resolver.py:301-303`), and `_validate_ref` then only checks that
   re-read base (`resolver.py:315-324`). A hg19 coordinate fed as hg38 whose asserted anchor
   disagrees with the reference passes silently — the exact wrong-build failure the
   fail-closed guarantee exists to catch, defeated precisely for insertions (a common
   therapeutic edit class).
3. **Liftover rebuilds a span from two independent endpoints.** `lift_interval` lifts only
   the two endpoints, keeps `start`'s strand, and never compares the lifted length to the
   source length (`coordinates.py:219-231`). A chain indel inside the interval silently
   resizes it; an inversion boundary splits the endpoints across strands and the code keeps
   one — producing a coordinate-scrambled interval instead of failing.
4. **Source-database build is silently overwritten.** `resolve` stamps the requested
   `build` (default `hg38`) onto every ClinVar/dbSNP record unconditionally
   (`resolver.py:386`); those parsers never record the record's native assembly
   (`clinvar.py:151`, `dbsnp.py:57`, model default `variant.py:99`). A GRCh37 release loaded
   with `build="hg38"` relabels every variant to hg38 with no liftover and no assertion —
   and, with no reference supplied, `_validate_ref` is skipped entirely
   (`resolver.py:387`). The mislabel then selects the VEP assembly (`effect.py:155-162`) and
   poisons provenance.

## What Changes

- **Reconcile contig naming at the reference/data boundary.** `BuildDescriptor`s declare
  their naming style; `ReferenceGenome` exposes it and either aliases `chr17`↔`17`
  transparently or rejects a style-mismatched fetch with an explicit **"contig-naming
  mismatch (chr-prefix)"** error, distinct from a base-level reference mismatch. Ambiguous-
  region flagging works regardless of naming style.
- **Validate an insertion's asserted anchor before re-anchoring**, and raise a
  reference-mismatch error when it disagrees, so left-alignment never masks a wrong-build
  insertion.
- **Fail liftover closed on a length change or strand split**: return `None` when the lifted
  span's length differs from the source beyond a declared tolerance, or the endpoints map to
  different strands.
- **Record each database record's native assembly** and raise (rather than overwrite) when
  the requested `build` disagrees, unless an explicit liftover is performed; provenance
  reflects the true source build.

## Impact

- Specs: `genome-access` (ADDED contig-naming reconciliation; MODIFIED liftover fail-closed
  conditions), `variant-resolution` (ADDED insertion-anchor validation; ADDED source-build
  reconciliation), `data-registry` (ADDED native-assembly recording).
- Code: `genome/reference.py`, `genome/coordinates.py`, `variant/resolver.py`,
  `variant/effect.py`, `data/clinvar.py`, `data/dbsnp.py`, `types/variant.py`.
- Tests: a `chr`-named lookup against an Ensembl-named reference aliases or errors clearly;
  an ambiguous region flags on either naming style; a wrong-build insertion raises; a
  liftover across a chain indel / inversion boundary returns `None`; a GRCh37 database with
  `build="hg38"` raises instead of relabeling.
