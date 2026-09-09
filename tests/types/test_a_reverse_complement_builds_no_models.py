"""Eleven call sites built two validated models to reverse-complement a string.

`str(DNASequence(x).reverse_complement())` appeared eleven times across the enumerators,
the genome index and the off-target scan. It constructs a frozen pydantic model,
validates the alphabet, translates, constructs a *second* model, validates the alphabet
again, and throws both away to return the string it started from.

The second validation was always redundant. `_COMPLEMENT` maps the IUPAC alphabet onto
itself — `test_every_validated_base_has_a_complement` pins exactly that — so the
complement of a validated sequence cannot hold a base the model would reject.

The first validation is *not* redundant, and dropping it is the trap already documented
beside `_COMPLEMENT_TABLE`: `str.translate` leaves an unmapped character unchanged where
the model raises. So `reverse_complement` validates once and translates once, and the
validation itself moved from a set difference to a `translate` — the same substitution
`_sanitize` uses, for the same reason.

Per `design()` on a 20 kb reference, exactly (call counts, not wall clock — this was
measured on a loaded machine and the timings were worthless):

    DNASequence.__init__        3,004  ->    778
    pydantic validate_python    4,989  ->  2,763
    Python calls              172,721 -> 163,482

Interleaved minimum over fifteen alternating runs: a 20 nt reverse complement 4.46 us ->
0.42 us (10.7x); a 2 Mb one 15.05 ms -> 10.20 ms (1.5x). The 2 Mb case is the off-target
scan's whole-contig complement, which ran twice per `scan_sequence`.

What this file pins is that the fast path answers the same question — including on the
inputs that must still raise, since a validator that stopped raising would be the silent
failure this project has already had once.
"""

from __future__ import annotations

import random

import pytest

from alleleforge.types.sequence import (
    _COMPLEMENT,
    _DROP_IUPAC_ALPHABET,
    IUPAC_ALPHABET,
    DNASequence,
    reverse_complement,
)


def test_the_drop_table_and_the_alphabet_describe_the_same_set() -> None:
    """The derivation guard, in the shape `_DROP_INDEX_ALPHABET` already uses.

    A literal table that lost a base would not raise; it would *accept* a base the model
    is supposed to reject, which is the direction that never shows up as an error.
    """
    assert set(_DROP_IUPAC_ALPHABET) == {ord(base) for base in IUPAC_ALPHABET}
    assert all(target is None for target in _DROP_IUPAC_ALPHABET.values())


def test_the_complement_cannot_produce_a_base_the_model_rejects() -> None:
    """Why the *second* validation was redundant, stated where it is relied upon."""
    assert set(_COMPLEMENT.values()) <= IUPAC_ALPHABET


@pytest.mark.parametrize(
    "sequence",
    ["", "A", "ACGT", "acgt", "NNNN", "RYSWKMBDHVN", "ACGTRYSWKMBDHVN" * 7],
)
def test_it_returns_what_the_two_model_form_returned(sequence: str) -> None:
    assert reverse_complement(sequence) == str(DNASequence(sequence).reverse_complement())


def test_it_agrees_with_the_two_model_form_on_random_valid_input() -> None:
    rng = random.Random(19)
    alphabet = "".join(sorted(IUPAC_ALPHABET))
    for _ in range(500):
        seq = "".join(rng.choice(alphabet) for _ in range(rng.randrange(0, 60)))
        seq = "".join(c.lower() if rng.random() < 0.3 else c for c in seq)
        assert reverse_complement(seq) == str(DNASequence(seq).reverse_complement())


@pytest.mark.parametrize("sequence", ["ACGX", "a-b", "ACGT ", "é", "ACGT\n", "1234"])
def test_it_still_refuses_what_the_model_refuses(sequence: str) -> None:
    """The failure mode a `translate` invites: an unmapped character passing through."""
    with pytest.raises(ValueError, match="non-IUPAC"):
        reverse_complement(sequence)
    with pytest.raises(ValueError):
        DNASequence(sequence)


def test_the_two_validators_reject_the_same_characters() -> None:
    """`translate`-emptiness must equal the set difference it replaced, character by
    character, over every code point a caller could plausibly pass."""
    for code in list(range(0, 128)) + [0xE9, 0x2013, 0x1F600]:
        text = chr(code)
        upper = text.upper()
        by_set = bool(set(upper) - IUPAC_ALPHABET)
        by_translate = bool(upper.translate(_DROP_IUPAC_ALPHABET))
        assert by_set == by_translate, (code, text)


def test_the_error_names_the_offending_characters() -> None:
    """It is the same message the model gave; a caller reads it to fix their input."""
    with pytest.raises(ValueError) as caught:
        reverse_complement("ACGZQ")
    assert "['Q', 'Z']" in str(caught.value)


@pytest.mark.parametrize("sequence", ["ACGT", "RYSWKM", "ACGTRYSWKMBDHVN"])
def test_it_is_still_an_involution(sequence: str) -> None:
    assert reverse_complement(reverse_complement(sequence)) == sequence


def test_no_call_site_kept_the_two_model_form() -> None:
    """The point of the change was the eleven sites, not the helper."""
    from pathlib import Path

    src = Path(__file__).resolve().parents[2] / "src" / "alleleforge"
    offenders = [
        path.relative_to(src).as_posix()
        for path in src.rglob("*.py")
        if "str(DNASequence(" in path.read_text() and path.name != "sequence.py"
    ]
    assert not offenders, offenders
