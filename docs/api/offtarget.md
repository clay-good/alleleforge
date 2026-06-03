# Off-target engine reference

The `alleleforge.offtarget` package (Phase 5) is AlleleForge's safety core:
population- and haplotype-aware off-target nomination behind one
[`search`][alleleforge.offtarget.engine.search] call. See
[Population-aware safety](../concepts/population.md) for the engine's five stages
and the reference-bias rationale.

!!! warning "Computational nominations"
    Off-target nominations are computational and **must be experimentally
    validated** (GUIDE-seq / CHANGE-seq / amplicon). The engine narrows the
    search; it does not replace confirmation.

## Engine

::: alleleforge.offtarget.engine

## Scoring (CFD, MIT, Cas12a)

::: alleleforge.offtarget.scoring

## Population augmentation

::: alleleforge.offtarget.population

## Haplotype-aware evaluation

::: alleleforge.offtarget.haplotype

## Cas-OFFinder cross-check

::: alleleforge.offtarget.cas_offinder_adapter
