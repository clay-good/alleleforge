# Genome access reference

The `alleleforge.genome` package (Phase 2) is pure infrastructure: strand-aware
reference retrieval, a content-addressed FM-index for PAM-anchored search, and
cross-build liftover plus hg38-ambiguous-region flagging. It knows about
sequence and coordinates, not CRISPR chemistry. All coordinates are 0-based
half-open.

## Reference genome access

::: alleleforge.genome.reference

## FM-index

::: alleleforge.genome.index

## Coordinates: liftover & ambiguous-region flagging

::: alleleforge.genome.coordinates

## Region files

`read_bed_intervals` reads a BED panel at BED's own convention — 0-based start, exclusive
end, headers and comments skipped — and refuses an interval naming no bases, the same
refusal `GenomicInterval.parse` makes for a locus string. It lived inline in the CLI,
which made a gene-panel scope reachable from one shell only and let the two spellings of
one restriction disagree: `--region chr1:100-100` was a usage error while the same row in
a BED file was accepted, and a scope of zero bases reports every guide as clean.

::: alleleforge.genome.bed
