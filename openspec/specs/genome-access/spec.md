# genome-access Specification

## Purpose

Provide strand-aware, bounds-checked, reproducible random access to reference genomes:
FASTA fetch with explicit coordinate conventions, content-addressed FM-indexing,
cross-build liftover, and flagging of hg38-difficult regions. Coordinates are 0-based
half-open internally; 1-based appears only at I/O boundaries.

## Requirements

### Requirement: Fetches use an explicit coordinate convention

The system SHALL reject any fetch, ambiguity-flag, or liftover whose interval is not
declared `ZERO_BASED_HALF_OPEN`, raising `ValueError`, so a coordinate-convention
mismatch can never be silently misread.

#### Scenario: Wrong convention
- **WHEN** an interval not tagged `ZERO_BASED_HALF_OPEN` is passed to `fetch_result`
- **THEN** it raises `ValueError`

#### Scenario: In-bounds plus-strand fetch
- **WHEN** a plus-strand interval fully inside a contig is fetched
- **THEN** the exact reference bases are returned and `padded` is `False`

### Requirement: Out-of-bounds fetches are N-padded, not fatal

A fetch running past a contig end (or before its start) SHALL be `N`-padded to the
requested length, exposing `left_pad`, `right_pad`, and a `padded` flag rather than
raising. An unknown contig SHALL raise `KeyError`.

#### Scenario: Overrun past contig end
- **WHEN** an interval extends beyond the contig end
- **THEN** the tail is `N`-filled and `right_pad > 0` with `padded = True`

#### Scenario: Unknown contig
- **WHEN** a contig name absent from the reference is fetched
- **THEN** it raises `KeyError`

### Requirement: Minus-strand fetches are reverse-complemented

A minus-strand fetch SHALL return the IUPAC-aware reverse complement of the plus-strand
bases.

#### Scenario: Minus strand
- **WHEN** a minus-strand interval is fetched
- **THEN** the returned sequence is the reverse complement of the plus-strand span

### Requirement: Reference downloads are consent- and checksum-gated

`from_build` SHALL refuse to download an uncached build unless `consent=True`
(`ConsentError`) and SHALL refuse any build whose pinned `sha256` is `None`
(`ChecksumError`); a downloaded artifact SHALL be SHA-256 verified before use. When a
build pins a `sha256`, an already-cached reference FASTA SHALL ALSO be re-verified against
it on load, and the FM-index cache SHALL expose an on-demand integrity check, so a
corrupted or externally-modified cached genome or index cannot be trusted silently.

#### Scenario: No consent
- **WHEN** `from_build` is asked to fetch an uncached build without consent
- **THEN** it raises `ConsentError`

#### Scenario: Unpinned checksum
- **WHEN** consent is given but the build's `sha256` is `None`
- **THEN** it raises `ChecksumError`

#### Scenario: Tampered cached reference
- **WHEN** a cached reference FASTA no longer matches its build's pinned `sha256`
- **THEN** loading it raises `ChecksumError`

### Requirement: FM-index construction is validated and content-addressed

`FMIndex.build` SHALL reject an empty sequence or any base outside `ACGTN`
(`ValueError`), warn above the 50,000,000-base threshold, and cache the index on disk
keyed by the SHA-256 of the indexed text; a matching cache is reused unless
`rebuild=True`.

#### Scenario: Illegal alphabet
- **WHEN** a sequence containing a non-`ACGTN` character is indexed
- **THEN** `build` raises `ValueError`

#### Scenario: Cache reuse
- **WHEN** an index for a given text already exists on disk and `rebuild` is `False`
- **THEN** the cached index is loaded instead of rebuilt

### Requirement: Suffix-array construction is native/Python byte-identical

The suffix array underlying the FM-index SHALL be byte-identical between the native
SA-IS kernel and the pure-Python fallback (guaranteed distinct suffixes via a unique
sentinel), so results do not depend on whether the compiled extension is present.

#### Scenario: Parity
- **WHEN** the same text is indexed with and without the native extension
- **THEN** the resulting suffix arrays are identical

### Requirement: hg38-difficult regions are flagged with a build recommendation

`flag_ambiguous_regions` SHALL recommend T2T-CHM13v2 only when the query overlaps a
flagged region AND `source_build == "hg38"`.

#### Scenario: Centromeric hg38 query
- **WHEN** an hg38 interval overlaps a flagged difficult region
- **THEN** a T2T-CHM13v2 recommendation with `recommended = True` is returned

### Requirement: Contig names are reconciled at the reference boundary

Each built-in `BuildDescriptor` SHALL declare its contig-naming style (Ensembl `1`/`MT`
versus UCSC `chr1`/`chrM`), and `ReferenceGenome` SHALL expose that style and reconcile a
fetch whose requested contig is named in the other style — either by transparently aliasing
`chr17`↔`17` (and `chrM`↔`MT`), or by raising an explicit "contig-naming mismatch
(chr-prefix)" error that is distinct from a base-level reference mismatch. Ambiguous-region
flagging SHALL fire regardless of which naming style the query uses.

#### Scenario: chr-prefixed query against an Ensembl-named reference
- **WHEN** a caller fetches `chr17` against a reference whose contig is named `17`
- **THEN** the fetch resolves via aliasing, or raises a contig-naming-mismatch error — never
  a `KeyError` and never a misleading "wrong build?" base mismatch

#### Scenario: Ambiguous region on either naming style
- **WHEN** a difficult hg38 locus is queried with either `chr1` or `1`
- **THEN** the T2T build recommendation is flagged, not silently suppressed

### Requirement: Liftover fails closed on ambiguous mappings

Liftover SHALL fail closed (return `None`) rather than emit a silently wrong coordinate.
`lift_interval` SHALL raise on an empty interval and SHALL return `None` when either endpoint
is unmapped, when the endpoints map to different contigs, when the endpoints map to
**different strands** (an inversion boundary), or when the **lifted span's length differs
from the source interval's length** beyond a declared tolerance (a chain indel inside the
interval) — so a resized or scrambled interval is never returned as if it covered the same
bases.

#### Scenario: Unmapped or cross-contig endpoint
- **WHEN** an interval endpoint has no mapping, or the endpoints map to different contigs
- **THEN** `lift_interval` returns `None`

#### Scenario: Chain indel inside the interval
- **WHEN** the chain contains an insertion or deletion within the interval so the lifted
  span length differs from the source length
- **THEN** `lift_interval` returns `None`

#### Scenario: Inversion boundary
- **WHEN** the two endpoints lift to opposite strands
- **THEN** `lift_interval` returns `None` rather than keeping one endpoint's strand
