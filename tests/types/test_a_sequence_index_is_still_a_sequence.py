"""Indexing a `DNASequence` returns a sequence, not a character.

The contract is in `__getitem__`'s docstring — *"integer indexing returns a
single-base sequence rather than a raw character, keeping the type uniform across the
codebase"* — and nothing asserted it. A type-guard sweep forced
`isinstance(key, slice)` to both answers in turn and the whole suite stayed green for
both, which was the tell: the branch's two arms were byte-identical, so it decided
nothing and no test could have distinguished them.

The branch is gone. The claim it hinted at is real and now has a test: an `int` key and
a `slice` key both come back as `DNASequence`, because every caller in this codebase
goes on to call sequence methods on the result and a bare `str` would fail somewhere
else entirely.
"""

from __future__ import annotations

import pytest

from alleleforge.types.sequence import DNASequence

_SEQ = "ACGTACGTNN"


@pytest.mark.parametrize("index", [0, 3, -1, 9])
def test_an_integer_index_returns_a_single_base_sequence(index: int) -> None:
    got = DNASequence(_SEQ)[index]
    assert isinstance(got, DNASequence), type(got)
    assert got.sequence == _SEQ[index]
    assert len(got) == 1


@pytest.mark.parametrize("key", [slice(0, 4), slice(4, None), slice(None, None, 2), slice(2, 2)])
def test_a_slice_returns_the_sub_sequence(key: slice) -> None:
    got = DNASequence(_SEQ)[key]
    assert isinstance(got, DNASequence), type(got)
    assert got.sequence == _SEQ[key]


def test_the_result_is_usable_as_a_sequence() -> None:
    """Why the wrap exists: a raw `str` would fail at the next call, not here."""
    assert DNASequence(_SEQ)[0:4].reverse_complement().sequence == "ACGT"
    assert DNASequence(_SEQ)[-1].is_ambiguous is True
    assert DNASequence(_SEQ)[0].is_ambiguous is False
