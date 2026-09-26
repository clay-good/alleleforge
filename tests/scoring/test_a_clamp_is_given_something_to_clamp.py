"""Hinges and clamps, measured on inputs that actually engage them.

The efficiency scorers are full of `max(0, …)` hinges and `max(0.0, …)/min(1.0, …)` clamps,
and mutation sweeps left survivors across all of them. The reason is uniform: every fixture
supplies a value the clamp does not touch, so the call is a no-op and swapping `max` for
`min` changes nothing. This is round 583's finding inverted — there, validators were tested
only *past* the boundary they admit; here, clamps are never given anything to clamp.

Only some of those survivors are reachable, and the distinction is the point of this file:

* `context_in_distribution`'s `len(seq) >= _MIN_CONTEXT_LENGTH` — reachable, and the
  boundary decides whether a 20-nt context is called out of distribution.
* the RuleSet3 baseline's **lower** interval clamp — reachable: a poly-T context scores
  0.032, so `value - 0.15` is negative and `max(0.0, …)` is what keeps the interval inside
  the domain an efficiency has.
* `_member_weights`' `[-1, 1]` range — reachable and stated in its docstring.
* the PridictScorer's long-RTT hinge — reachable at 21 nt.

The rest are **unreachable through the public API**, and are recorded here rather than
given a test that would have to fake a value the scorer cannot produce. The RuleSet3
baseline's upper clamp needs `value > 0.85` and the scorer's range tops out near 0.61; the
PridictScorer's lower clamp needs `value < 0.15` and its lowest value over every valid
PBS x RTT x GC combination is 0.273, with a maximum near 0.67, so its `min(1.0, …)` and its
`min(0.99, …)` chromatin cap cannot engage either. Those mutants are equivalent, not gaps —
the clamps are defensive code for a range these scorers do not reach, which is a reasonable
thing for them to be, and not something a test can assert from outside.
"""

from __future__ import annotations

import pytest

from alleleforge.scoring.cas9_efficiency import (
    _MIN_CONTEXT_LENGTH,
    RuleSet3Scorer,
    _member_weights,
    context_in_distribution,
)
from alleleforge.scoring.prime_efficiency import PridictScorer
from alleleforge.types.guide import PegRNA, Spacer
from alleleforge.types.sequence import DNASequence

#: The documented heuristic half-width of the baseline scorers' intervals.
_HALF = 0.15


# -- the out-of-distribution length boundary -----------------------------------


def test_a_context_exactly_at_the_minimum_length_is_in_distribution() -> None:
    """`len(seq) >= _MIN_CONTEXT_LENGTH` admits the minimum itself.

    Tightened to `>`, a context of exactly the minimum length is called out of
    distribution — which demotes the candidate to its lower interval bound in the ranker
    and raises `ood` on the report, for an input the model was defined on.
    """
    assert context_in_distribution("A" * _MIN_CONTEXT_LENGTH) is True
    assert context_in_distribution("A" * (_MIN_CONTEXT_LENGTH - 1)) is False


def test_an_ambiguous_base_is_out_of_distribution_at_any_length() -> None:
    """The other half of the conjunction, so neither term can be the only one tested."""
    assert context_in_distribution("N" + "A" * _MIN_CONTEXT_LENGTH) is False
    assert context_in_distribution("A" * 30) is True


# -- the interval clamp that does engage ---------------------------------------


def test_a_low_scoring_context_has_its_interval_clamped_to_zero() -> None:
    """`max(0.0, value - half)` on an input where `value - half` is negative.

    A poly-T context scores about 0.03, so the unclamped lower bound is about -0.12 — not
    an efficiency. Every other fixture in the suite sits above 0.15, where the clamp is a
    no-op and `max` and `min` agree.
    """
    prediction = RuleSet3Scorer().score("T" * 30)
    assert prediction.value < _HALF, "the fixture must reach past the clamp to measure it"
    assert prediction.interval[0] == 0.0
    assert prediction.interval[1] == pytest.approx(prediction.value + _HALF)


def test_every_baseline_interval_stays_inside_the_efficiency_domain() -> None:
    """The invariant the clamps exist for, over a spread of real contexts."""
    scorer = RuleSet3Scorer()
    for context in ("A" * 30, "T" * 30, "G" * 30, "C" * 30, "GC" * 15, "AT" * 15):
        low, high = scorer.score(context).interval
        assert 0.0 <= low <= high <= 1.0, f"{context[:6]}… gave an interval outside [0, 1]"


# -- the deterministic member weights ------------------------------------------


def test_member_weights_span_minus_one_to_one() -> None:
    """`(raw / 0xFFFFFFFF) * 2.0 - 1.0` maps a hash onto `[-1, 1]`, as documented.

    The arithmetic had no check at all, so dropping the `* 2.0` or the `- 1.0` — which
    moves every projection weight into `[0, 1]` and makes the ensemble's members
    systematically agree — changed nothing.
    """
    weights = _member_weights(0, 256)
    assert len(weights) == 256
    assert all(-1.0 <= w <= 1.0 for w in weights)
    assert min(weights) < -0.5, "the range must reach below zero, not just [0, 1]"
    assert max(weights) > 0.5
    # Deterministic, and different per member — the point of seeding by index.
    assert _member_weights(0, 32) == _member_weights(0, 32)
    assert _member_weights(0, 32) != _member_weights(1, 32)


# -- the long-RTT hinge --------------------------------------------------------


def _pegrna(rtt_len: int, pbs_len: int = 13) -> PegRNA:
    gc = pbs_len // 2
    return PegRNA(
        spacer=Spacer(sequence=DNASequence("A" * 20)),
        scaffold=DNASequence("GTTTAGAGCTAGAAATAGCAAG"),
        rtt=DNASequence("A" * rtt_len),
        pbs=DNASequence("G" * gc + "A" * (pbs_len - gc)),
        rtt_homology_3prime=6,
    )


def test_the_long_rtt_penalty_starts_past_twenty_nucleotides() -> None:
    """`max(0, len(rtt) - 20)` is a hinge: flat at or below 20, falling beyond it.

    Every fixture used an RTT inside 20, where the hinge is 0 and the term vanishes. With
    `min` in its place the term is *negative* below 20, so a short RTT earns a bonus and
    the penalty the comment describes ("very long RTTs are penalized") inverts into a
    reward for the geometry it was written to discourage.
    """
    scorer = PridictScorer()
    at_16 = scorer.score(_pegrna(16)).value
    at_20 = scorer.score(_pegrna(20)).value
    at_21 = scorer.score(_pegrna(21)).value
    at_30 = scorer.score(_pegrna(30)).value

    assert at_16 == pytest.approx(at_20), "below the hinge the RTT length must not matter"
    assert at_21 < at_20, "past the hinge a longer RTT must score lower"
    assert at_30 < at_21, "and the penalty must keep growing"


def test_the_rtt_penalty_is_monotonic_past_the_hinge() -> None:
    """Sign and direction together, so a flipped subtraction is named."""
    scorer = PridictScorer()
    values = [scorer.score(_pegrna(n)).value for n in (21, 24, 27, 30, 33)]
    assert values == sorted(values, reverse=True)


# -- the mid-GC PBS preference -------------------------------------------------


def _pbs_pegrna(gc_count: int, pbs_len: int = 12) -> PegRNA:
    return PegRNA(
        spacer=Spacer(sequence=DNASequence("A" * 20)),
        scaffold=DNASequence("GTTTAGAGCTAGAAATAGCAAG"),
        rtt=DNASequence("A" * 16),
        pbs=DNASequence("G" * gc_count + "A" * (pbs_len - gc_count)),
        rtt_homology_3prime=6,
    )


def test_a_mid_gc_pbs_scores_highest_and_the_falloff_is_symmetric() -> None:
    """`2.0 * abs(_gc(pbs) - 0.5)` — "mid-GC PBS primes best", as the comment says.

    Every other fixture in this file holds GC at one value, so the term is a constant and
    the mutation is invisible. Changing the subtraction to an addition turns `abs(gc - 0.5)`
    into `gc + 0.5`, which is monotonic in GC: the preference stops being for the middle
    and becomes a preference for GC-poor primers, ranking pegRNAs by a property the model
    was not built to prefer.

    Asserted as a shape rather than as numbers: a peak at 0.5 and a symmetric falloff,
    which no monotonic substitute can produce.
    """
    scorer = PridictScorer()
    at = {gc: scorer.score(_pbs_pegrna(gc)).value for gc in (0, 2, 4, 6, 8, 10, 12)}

    assert at[6] == max(at.values()), "the optimum must be the mid-GC primer"
    # Strictly falling away from the middle in both directions.
    assert at[6] > at[4] > at[2] > at[0]
    assert at[6] > at[8] > at[10] > at[12]
    # And symmetric, since the term depends on the distance from 0.5 and not its sign.
    for low, high in ((4, 8), (2, 10), (0, 12)):
        assert at[low] == pytest.approx(at[high]), f"GC {low}/12 and {high}/12 must score alike"
