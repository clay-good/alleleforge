"""The seed prefilter cost more than the work it skipped, and ran by default.

Twin of `test_the_default_scan_path_is_the_fast_one`, and the same failure: a number in
`scripts/native_speedup.py`'s output disagreeing with a decision in the prose. The script
prints the pair — `high-stringency (mismatches=1): brute force 29.89ms, seeded 68.16ms
(0.4x)` — and `scan_sequence` seeded anyway.

The prefilter's saving is the anchors it skips; its cost is its own `O(n)` pass over the
sequence. Every round that measured it found the saving smaller: ~2-4x when the threshold
was calibrated, then 0.94-1.12x once the per-anchor alignment got cheaper. The last of it
went when the PAM test became one compiled regex scan, because the prefilter then pruned
only a native `evaluate_anchor` call — which is cheaper than deciding not to make it.

Measured at 1 Mb, one guide, no bulges, three runs each, brute force / seeded, in ms:

    crate built      48/139   45/156   39/167   58/157     (mm = 0, 1, 2, 3)
    crate not built  60/226   80/212   69/292   81/282

    `aforge offtarget` over 20 Mb at `--mismatches 1 --dna-bulges 0 --rna-bulges 0`
    5.89 / 6.50 / 5.90 s  ->  3.42 / 3.18 / 2.83 s, byte-identical JSON

The previous comment on `MIN_SELECTIVE_K` left one repair open — "making it pay again
would mean attacking the prefix-sum construction". That was measured too: a `bisect` over
the seed positions, with no `O(n)` pass at all, is 0.79-1.65x with the crate and
1.82-2.66x without it. Still a loss almost everywhere.

So it is opt-in, not deleted: the prefilter is a *proven superset* (pigeonhole — some
uncut substitution-free block of length `k` survives any in-budget alignment), and that
exactness is why it stays reachable and parity-tested. What is removed is the assumption
that it is free.

This file pins the shape, not a wall-clock number: timings are hardware dependent and
belong in the script, but "the default scan does not seed" is a property, and so is
"asking for it still works and finds the same hits".
"""

from __future__ import annotations

import random

import pytest

from alleleforge.offtarget._search import (
    MIN_SELECTIVE_K,
    SEED_PREFILTER_AUTO_ENGAGES,
    _seed_filter,
    scan_sequence,
)
from alleleforge.types.guide import PAM

_PAM = PAM(pattern="NGG")
_SPACER = "GACGTTGCAAGGCTTACCGT"


@pytest.fixture
def sequence() -> str:
    """A contig long enough to hold hits at several budgets."""
    rng = random.Random(4)
    seq = list("".join(rng.choice("ACGT") for _ in range(6000)))
    # Plant the on-target and two near-relatives so the budgets below differ.
    for at, spacer in (
        (1000, _SPACER),
        (3000, "GACGTTGCAAGGCTTACCGA"),
        (5000, "GACGTTGCAAGCCTTACCGA"),
    ):
        seq[at : at + len(spacer) + 3] = list(spacer + "AGG")
    return "".join(seq)


def test_the_prefilter_is_opt_in() -> None:
    """No budget makes it engage itself; that is the whole change."""
    assert SEED_PREFILTER_AUTO_ENGAGES is False


#: Budgets whose seed is selective enough that the prefilter would have engaged. At the
#: *default* budget it never did — `seed_length(20, 4 + 1 + 1)` falls below
#: `MIN_SELECTIVE_K` — so a test that only used the default would pass either way.
_SELECTIVE_BUDGETS = ((0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0))


@pytest.mark.parametrize(("mismatches", "dna_bulges", "rna_bulges"), _SELECTIVE_BUDGETS)
def test_these_budgets_are_ones_the_prefilter_would_have_engaged_on(
    sequence: str, mismatches: int, dna_bulges: int, rna_bulges: int
) -> None:
    """Or the parity check below proves nothing about the path that changed."""
    covered = _seed_filter(
        _SPACER, sequence, max_mm=mismatches, dna_bulges=dna_bulges, rna_bulges=rna_bulges
    )
    assert covered is not None, "this budget never seeded; it cannot show the change"


def test_the_default_budget_never_seeded_anyway() -> None:
    """Stated so the parametrization above is not mistaken for the common case."""
    assert _seed_filter(_SPACER, "ACGT" * 500, max_mm=4, dna_bulges=1, rna_bulges=1) is None, (
        f"the default budget now seeds; MIN_SELECTIVE_K={MIN_SELECTIVE_K}"
    )


@pytest.mark.parametrize(("mismatches", "dna_bulges", "rna_bulges"), _SELECTIVE_BUDGETS)
def test_asking_for_it_finds_exactly_what_the_default_finds(
    sequence: str, mismatches: int, dna_bulges: int, rna_bulges: int
) -> None:
    """The path stays reachable and exact — only the default changed."""
    budget = {"mismatches": mismatches, "dna_bulges": dna_bulges, "rna_bulges": rna_bulges}
    default = scan_sequence("chr1", sequence, _SPACER, _PAM, **budget)
    seeded = scan_sequence("chr1", sequence, _SPACER, _PAM, seed=True, **budget)
    brute = scan_sequence("chr1", sequence, _SPACER, _PAM, seed=False, **budget)
    assert default == brute, "the default is no longer the unseeded scan"
    assert seeded == brute, "the prefilter is no longer a proven superset"
    assert default, "the fixture produced no hits; the comparison is vacuous"
