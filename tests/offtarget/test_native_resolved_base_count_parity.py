"""The searched-base count, in one pass instead of eight, with the same answer.

`_resolved_base_count` is what a report means by "over N bases": the unambiguous A/C/G/T
of the region actually scanned, so an `N`-padded assembly gap cannot be counted as
searched. It made eight `str.count` passes over the contig — both cases of four bases —
and its docstring argued, correctly and with measurements, that eight passes were
negligible beside the scan.

The scan has since become several times faster, and the eight passes had grown to about a
fifth of it. The kernel does the same count in one pass and, like the Python, **without
upper-casing first**: a copy of a chromosome is a quarter-gigabyte transient in a path
whose whole design is bounded memory.

Both cases stay counted on both paths. The upper-casing on the way in is a `pyfaidx`
default rather than an invariant of this repository, and if it changed, a repeat-masked
genome would report almost nothing as searchable — the false alarm exactly inverse to the
one this count exists to raise.
"""

from __future__ import annotations

import random

import pytest

from alleleforge.offtarget.engine import _NATIVE_RESOLVED_BASE_COUNT, _resolved_base_count

requires_native = pytest.mark.skipif(
    _NATIVE_RESOLVED_BASE_COUNT is None,
    reason="native aforge_native resolved_base_count kernel not built",
)


def _python(sequence: str) -> int:
    return sum(sequence.count(base) for base in "ACGTacgt")


@pytest.mark.native
@requires_native
def test_randomized_sequences_agree() -> None:
    rng = random.Random(20240501)
    for _ in range(500):
        # Deliberately not just ACGTN: a real FASTA can carry IUPAC codes, and the
        # question is "unambiguous", not "not an N".
        alphabet = "ACGTNacgtnRYSWKMBDHVryswkmbdhv-*"
        sequence = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 300)))
        assert _NATIVE_RESOLVED_BASE_COUNT(sequence) == _python(sequence), sequence


@pytest.mark.native
@requires_native
def test_the_lowercase_half_is_not_dropped() -> None:
    """A repeat-masked genome is lowercase, and it is searched like any other."""
    assert _NATIVE_RESOLVED_BASE_COUNT("acgtACGT") == 8
    assert _NATIVE_RESOLVED_BASE_COUNT("acgtNNNN") == 4


def test_the_dispatcher_returns_the_same_answer_either_way() -> None:
    """Whatever is installed, the function the engine calls must agree with the Python."""
    for sequence in ("", "N" * 10, "ACGT" * 25, "acgtRYN" * 7, "A" + "N" * 50 + "t"):
        assert _resolved_base_count(sequence) == _python(sequence), sequence
