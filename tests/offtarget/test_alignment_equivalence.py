"""Differential guard on the off-target scan's innermost alignment.

``_best_with_removed_base`` prices every single-base-removal alignment of a
bulged window. The obvious implementation rebuilds and fully re-compares the
string once per removal position; the shipped one derives the same counts from a
prefix and a suffix sum in two linear passes. That rewrite is a pure
optimization on the hottest function of the safety-critical off-target scan — it
runs twice for every PAM-positive anchor in the search space — so its output must
be *identical*, not merely similar: the chosen mismatch count feeds the
specificity score, and the chosen removal position feeds the reported alignment.

The shipped version also bails out of both passes as soon as the running
mismatch count passes the budget, which prunes most windows after a handful of
bases. That bail is only sound because each count is monotone in its direction,
so the randomized inputs below deliberately span budgets from 0 (bail
immediately) to 10 (never bail) and lengths from 0 to 24.

The oracle here is the naive implementation, kept verbatim.
"""

from __future__ import annotations

import random

import pytest

from alleleforge.offtarget._search import _best_ungapped, _best_with_removed_base


def _naive(longer: str, shorter: str, max_mm: int) -> tuple[int, str] | None:
    """Rebuild-and-compare every removal; the definition the fast path must match."""
    best: tuple[int, str] | None = None
    for r in range(len(longer)):
        reduced = longer[:r] + longer[r + 1 :]
        mm = sum(a != b for a, b in zip(reduced, shorter, strict=True))
        if mm <= max_mm and (best is None or mm < best[0]):
            best = (mm, reduced)
    return best


def test_matches_the_naive_definition_over_randomized_inputs() -> None:
    rng = random.Random(20260905)
    for _ in range(25_000):
        n = rng.randint(0, 24)
        shorter = "".join(rng.choice("ACGTN") for _ in range(n))
        longer = "".join(rng.choice("ACGTN") for _ in range(n + 1))
        max_mm = rng.randint(0, 10)
        assert _best_with_removed_base(longer, shorter, max_mm) == _naive(longer, shorter, max_mm)


@pytest.mark.parametrize(
    ("longer", "shorter", "max_mm"),
    [
        ("A", "", 0),  # degenerate: removing the only base leaves an empty match
        ("AA", "A", 0),  # a tie must keep the earliest removal position
        ("ACGT", "ACG", 0),  # the removal is at the end
        ("ACGT", "CGT", 0),  # the removal is at the start
        ("AAAA", "TTT", 0),  # never in budget
        ("AAAA", "TTT", 3),  # in budget only at the ceiling
    ],
)
def test_edges_match_the_naive_definition(longer: str, shorter: str, max_mm: int) -> None:
    assert _best_with_removed_base(longer, shorter, max_mm) == _naive(longer, shorter, max_mm)


def test_ungapped_matches_the_naive_definition_over_randomized_inputs() -> None:
    """`_best_ungapped` stops counting once the budget is blown; that must not show.

    The naive definition prices all N positions and then compares. Stopping early is
    equivalent *because* an over-budget alignment is discarded — its true count is never
    read — but that is an argument, and this is the check. It matters more than it looks:
    this is the innermost comparison of the whole scan, about half a million calls over
    2 Mb, and a wrong count here becomes a wrong mismatch number on a reported
    off-target site.

    The optimization is worth having: 60% faster in isolation at the default 4-mismatch
    budget, and 10-16% off a whole scan depending on the bulge configuration.
    """
    rng = random.Random(20260906)
    for _ in range(25_000):
        n = rng.randint(1, 24)
        spacer = "".join(rng.choice("ACGTN") for _ in range(n))
        # Mostly random windows, sometimes a near-match, so both branches are hit.
        if rng.random() < 0.3:
            window = list(spacer)
            for _ in range(rng.randint(0, 5)):
                window[rng.randrange(n)] = rng.choice("ACGTN")
            candidate = "".join(window)
        else:
            candidate = "".join(rng.choice("ACGTN") for _ in range(n))
        max_mm = rng.randint(0, 10)

        naive = sum(a != b for a, b in zip(spacer, candidate, strict=True))
        expected = naive if naive <= max_mm else None

        assert _best_ungapped(spacer, candidate, max_mm) == expected, (
            spacer,
            candidate,
            max_mm,
        )


def test_ungapped_still_rejects_a_length_mismatch() -> None:
    """The `strict=True` zip was load-bearing: an unequal pair is a caller bug."""
    with pytest.raises(ValueError):
        _best_ungapped("ACGT", "ACG", 4)
