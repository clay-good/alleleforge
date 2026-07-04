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
(`ChecksumError`); a downloaded artifact SHALL be SHA-256 verified before use.

#### Scenario: No consent
- **WHEN** `from_build` is asked to fetch an uncached build without consent
- **THEN** it raises `ConsentError`

#### Scenario: Unpinned checksum
- **WHEN** consent is given but the build's `sha256` is `None`
- **THEN** it raises `ChecksumError`

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

### Requirement: Liftover fails closed on ambiguous mappings

`Liftover.lift_interval` SHALL raise on an empty interval and SHALL return `None` when
either endpoint fails to map or the endpoints land on different contigs.

#### Scenario: Endpoint unmapped
- **WHEN** either interval endpoint has no mapping in the target build
- **THEN** `lift_interval` returns `None`
