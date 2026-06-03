# Core types reference

The `alleleforge.types` package is the typed vocabulary the whole system speaks: strandedness,
coordinate systems, ambiguity codes, the uncertainty contract, and every serializable result type.
Coordinates are 0-based half-open internally.

JSON Schemas for every public model are emitted to `docs/schemas/` by `scripts/export_schemas.py`.

## Sequences & coordinates

::: alleleforge.types.sequence

## Variants

::: alleleforge.types.variant

## Guides, base-edit windows, pegRNAs

::: alleleforge.types.guide

## Edits & outcomes

::: alleleforge.types.edit

## Off-target sites & reports

::: alleleforge.types.offtarget

## The uncertainty contract

::: alleleforge.types.prediction

## Design candidates & menus

::: alleleforge.types.candidate

## Provenance

::: alleleforge.types.provenance
