# SpCas9 nuclease reference

Phase 7 is the first full chemistry vertical — **enumerate → efficiency →
outcome → off-target → candidate** — proving the pipeline end to end on the most
mature chemistry. From a resolved variant, [`design_cas9`][alleleforge.design.cas9.design_cas9]
returns scored [`DesignCandidate`][alleleforge.types.candidate.DesignCandidate]s,
each carrying a calibrated efficiency interval, a predicted indel spectrum, and an
ancestry-stratified off-target report.

!!! note "Transparent baselines, swappable for trained models"
    The shipped efficiency and outcome models are transparent, weight-free
    baselines (a Rule-Set-3-style feature model; a microhomology/MMEJ spectrum
    model) so the vertical runs in CI without downloads. The trained Rule Set 3,
    inDelphi, Lindel, and X-CRISP models load through the license-gated model zoo,
    and the default efficiency scorer is the backbone deep ensemble.

## Guide enumeration

::: alleleforge.enumerate.cas9

## On-target efficiency

::: alleleforge.scoring.cas9_efficiency

## Edit-outcome (indel spectrum)

::: alleleforge.scoring.cas9_outcome

## The design vertical

::: alleleforge.design.cas9
