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
