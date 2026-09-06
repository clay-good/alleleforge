"""Folding a contig to the index alphabet must not change what it folds to.

`_sanitize` maps every base outside `ACGTN` to `N` so the linear scan and the
FM-index/native path agree about what a window contains. It did that with a per-base
Python loop over the whole contig — `all(b in _INDEX_ALPHABET for b in seq)` and then a
comprehension — which is one pass of interpreter overhead per character of a reference.

    2 Mb   old 62.7ms   new  3.0ms
    20 Mb  old 775.4ms  new 35.2ms

It is called once per sequence per `search()`, uncached, and `search()` runs once per
candidate in a design, so the saving is per candidate per contig.

`str.translate` does both halves in C. The detection deletes every in-alphabet base and
asks whether anything is left; the substitution then derives its table from the strays
themselves, which is what makes it faster on *every* input distribution rather than
buying the clean path with the dirty one (2 Mb clean +92%, one stray base +94%, a
synthetic 44%-IUPAC sequence +78%).

Deriving the table from the data also avoids the trap a fixed 256-entry table would
have: a non-ASCII byte would fall outside it and pass through unfolded. Here a
character absent from the table is by construction in the alphabet.

This file pins the equivalence, because the substitution is only safe while
`_DROP_INDEX_ALPHABET` and `_INDEX_ALPHABET` describe the same set — and the failure
mode of them diverging is not an exception, it is a contig folded wrongly and scanned
without complaint.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from alleleforge.offtarget._search import (
    _DROP_INDEX_ALPHABET,
    _INDEX_ALPHABET,
    _sanitize,
)


def _reference(seq: str) -> str:
    """The pre-optimization implementation, kept as the definition of correct."""
    if all(b in _INDEX_ALPHABET for b in seq):
        return seq
    return "".join(b if b in _INDEX_ALPHABET else "N" for b in seq)


@given(st.text(alphabet="ACGTNRYSWKMBDHVacgtn .-", max_size=400))
def test_it_agrees_with_the_definition_on_sequence_like_text(seq: str) -> None:
    assert _sanitize(seq) == _reference(seq)


@given(st.text(max_size=200))
def test_it_agrees_on_arbitrary_text(seq: str) -> None:
    """Including non-ASCII, which a fixed byte table would have passed through."""
    assert _sanitize(seq) == _reference(seq)


@pytest.mark.parametrize(
    "seq",
    [
        "",
        "ACGTN",
        "acgtn",
        "ACGT\n",
        "ÅÄÖ",
        "A" * 50 + "Ñ" + "C" * 50,
        "R",
        "N" * 100,
        "ACGT" * 100 + "Y",
    ],
)
def test_hand_written_shapes(seq: str) -> None:
    assert _sanitize(seq) == _reference(seq)


def test_the_deletion_table_covers_exactly_the_alphabet() -> None:
    """The precondition the substitution rests on.

    Every in-alphabet character must be deleted (so a clean contig leaves nothing
    behind) and nothing else may be, or a stray would be dropped from the detection
    and silently left unfolded.

    Deriving the table from `_INDEX_ALPHABET` makes this true by construction, so
    today this passes for free. It is here for the edit that replaces the derivation
    with a written-out table — the tempting kind, because a literal is easier to
    read — whose failure mode is not an exception but a base the index can hold
    being folded to `N`.
    """
    assert {chr(o) for o in _DROP_INDEX_ALPHABET} == set(_INDEX_ALPHABET)
    assert all(_DROP_INDEX_ALPHABET[ord(b)] is None for b in _INDEX_ALPHABET)


def test_a_table_that_lost_a_base_is_caught() -> None:
    """Guard the guard, on a hand-built table rather than the derived one.

    Mutating `_INDEX_ALPHABET` proves nothing while the table is derived from it —
    both sides move together. What the check must catch is a *table* that no longer
    matches the alphabet, so that is what is constructed here.
    """
    lost = str.maketrans("", "", "ACGT")  # missing N
    assert {chr(o) for o in lost} != set(_INDEX_ALPHABET)
    # And such a table would leave the alphabet's own `N` behind, tripping the
    # detection into a needless rebuild on a perfectly clean contig.
    assert "NNN".translate(lost) == "NNN"
    assert "NNN".translate(_DROP_INDEX_ALPHABET) == ""
