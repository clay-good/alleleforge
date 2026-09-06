# Designer: routing, candidate menu & ranking

Phase 10 is the **orchestrator** that realizes AlleleForge's variant-first
promise: from one variant, decide which chemistries are eligible, generate
candidates from each, score them on one footing, and return a ranked, explained
menu.

[`design`][alleleforge.design.designer.design] takes any resolver input form (or
an already-resolved variant) and returns a
[`RankedMenu`][alleleforge.types.candidate.RankedMenu]:

1. **Resolve** the variant (Phase 4).
2. **Route** to the biologically eligible chemistries (transparent rules below).
3. **Enumerate and score** candidates per chemistry — each with a calibrated
   efficiency interval, a predicted outcome distribution, and an
   ancestry-stratified off-target report (Phases 5, 7-9).
4. **Rank** them across chemistries with a transparent weighted sum and a
   Pareto front.
5. **Stamp provenance** so the whole menu is reproducible from its inputs.

!!! note "Graceful degradation is the contract"
    If a chemistry's model is unavailable, its enumeration raises, or it simply
    finds nothing actionable, the designer records *why* in the menu rationale
    and continues with the rest. A returned menu always carries either a
    candidate per eligible chemistry or an explicit reason it does not.

## Routing

`eligible_chemistries(resolved, intent)` applies a small table of transparent,
inspectable rules — each pairing a chemistry with a one-line biological rationale
and a pure predicate. Use [`route`][alleleforge.design.routing.route] for the
full per-chemistry verdict (kept *and* dropped, with reasons).

| Chemistry | Eligible when | Why |
|---|---|---|
| Base editing (ABE) | A transition SNV whose required change is `A:T->G:C` | Installs one transition in-window, no double-strand break — the cleanest fix |
| Base editing (CBE) | A transition SNV whose required change is `G:C->A:T` | Same, for the complementary transition |
| Prime editing | Any precise small edit — SNV, MNV, insertion, deletion, delins — on a non-disruptive intent, with the replaced reference span ≤ `PRIME_MAX_EDIT` (44) and the **written** allele ≤ `PRIME_MAX_TEMPLATED_EDIT` (29) | Writes the edit from a variable-length RT template with no break. A deleted span costs no template, so the binding bound is on what the RTT must write, not on what it replaces |
| SpCas9 nuclease | Disruption (knock-out) intent; **or** a precise edit no break-free chemistry can reach | A break repaired by NHEJ yields frameshifting indels — the knock-out route. For a precise edit it needs an HDR donor and is inefficient, S/G2-restricted, and dominated by NHEJ byproducts, so it is offered only as the **last resort** (e.g. restoring a deletion longer than any RT template can write) |

::: alleleforge.design.routing

## Ranking

The ranker projects every candidate — regardless of chemistry — onto four
shared, higher-is-better objectives and orders them by a transparent weighted
sum, while also exposing the Pareto front for users who weight the objectives
differently.

| Objective | Definition | Default weight |
|---|---|---|
| Efficiency | Calibrated on-target efficiency point estimate | 0.35 |
| Cleanliness | Probability mass on the intended allele | 0.30 |
| Safety | `1 - off-target score` of the **worst-affected ancestry** | 0.30 |
| Simplicity | Reagent simplicity (single sgRNA > pegRNA + nick + motif) | 0.05 |

!!! warning "Safety is computed against the worst-affected ancestry"
    The safety term uses the highest off-target score across ancestries, never
    the average — so a guide that is safe on one population but dangerous in
    another is correctly down-ranked instead of hidden behind a global number.

::: alleleforge.design.ranking

## The designer

::: alleleforge.design.designer


## Cohort-scale batch design

`design_many` is the cohort multiplier over `design`: it streams the input so memory
stays bounded, isolates per-item failures, and is resumable from a JSONL run manifest.

::: alleleforge.design.cohort

## Spacer quality

Pol III transcription caveats, shared by every chemistry — they are properties of a
spacer as a transcribed reagent, not of the chemistry holding it.

::: alleleforge.design.spacer_quality

## Shared candidate caveats

Off-target caveats are a property of the spacer against the genome, not of the
chemistry carrying it, so every vertical derives them from one helper.

::: alleleforge.design.offtarget_flags
