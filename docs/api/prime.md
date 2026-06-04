# Prime editing reference

Phase 9 is the **flagship**: the chemistry where AlleleForge contributes the most.
No existing open-source tool combines all four axes for prime editing — therapeutic
variant input, ML efficiency with calibrated uncertainty, outcome/byproduct
prediction, and population-aware off-target. AlleleForge unifies them.

From a resolved variant, [`design_prime`][alleleforge.design.prime.design_prime]
enumerates pegRNAs (PBS 8-17 nt; RTT 7-34 nt covering the edit + >= 5 nt 3'
homology; a tevopreQ1 epegRNA motif; a PE3/PE3b nicking guide), scores efficiency
and outcome with calibrated uncertainty, runs the off-target engine on **both**
nicks (merged into one ancestry-stratified report), and returns ranked candidates.

!!! warning "Honest out-of-distribution flagging"
    PRIDICT2.0 is trained on HEK293T/K562. Any cell context unlike that training
    distribution sets `in_distribution=False` on the efficiency prediction and
    raises an `ood` flag — surfaced prominently, because a confident efficiency
    number outside the training context is exactly the false confidence the
    uncertainty contract exists to prevent.

!!! note "Transparent baselines, swappable for trained models"
    The shipped efficiency and outcome models are transparent, weight-free
    baselines so the vertical runs in CI without downloads. The trained PRIDICT2.0
    (with ePRIDICT chromatin adjustment), DeepPrime, and GenET models load through
    the license-gated model zoo.

## pegRNA enumeration

::: alleleforge.enumerate.prime

## Efficiency (PRIDICT2.0)

::: alleleforge.scoring.prime_efficiency

## Outcome (intended vs. byproduct)

::: alleleforge.scoring.prime_outcome

## The design vertical

::: alleleforge.design.prime
