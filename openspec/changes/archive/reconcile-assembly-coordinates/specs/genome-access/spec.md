## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Liftover fails closed on ambiguous mappings

Liftover SHALL fail closed (return `None`) rather than emit a silently wrong coordinate.
`lift_interval` SHALL return `None` when either endpoint is unmapped, when the endpoints map
to different contigs, when the endpoints map to **different strands** (an inversion
boundary), or when the **lifted span's length differs from the source interval's length**
beyond a declared tolerance (a chain indel inside the interval) — so a resized or scrambled
interval is never returned as if it covered the same bases.

#### Scenario: Unmapped or cross-contig endpoint
- **WHEN** an interval endpoint does not map, or the endpoints map to different contigs
- **THEN** `lift_interval` returns `None`

#### Scenario: Chain indel inside the interval
- **WHEN** the chain contains an insertion or deletion within the interval so the lifted
  span length differs from the source length
- **THEN** `lift_interval` returns `None`

#### Scenario: Inversion boundary
- **WHEN** the two endpoints lift to opposite strands
- **THEN** `lift_interval` returns `None` rather than keeping one endpoint's strand
