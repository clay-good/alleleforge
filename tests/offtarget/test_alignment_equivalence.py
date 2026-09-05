"""Differential guard on the off-target scan's innermost alignment.

``_best_with_removed_base`` prices every single-base-removal alignment of a
bulged window. The obvious implementation rebuilds and fully re-compares the
string once per removal position; the shipped one derives the same counts from a
prefix and a suffix sum in two linear passes. That rewrite is a pure
optimization on the hottest function of the safety-critical off-target scan — it
runs twice for every PAM-positive anchor in the search space — so its output must
be *identical*, not merely similar: the chosen mismatch count feeds the
specificity score, and the chosen removal position feeds the reported alignment.

The oracle here is the naive implementation, kept verbatim.
"""

from __future__ import annotations

import random

import pytest

from alleleforge.offtarget._search import _best_with_removed_base


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
    for _ in range(4000):
        n = rng.randint(0, 22)
        shorter = "".join(rng.choice("ACGTN") for _ in range(n))
        longer = "".join(rng.choice("ACGTN") for _ in range(n + 1))
        max_mm = rng.randint(0, 8)
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
