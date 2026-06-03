"""Tests for sequence value objects: DNASequence, intervals, strand."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from alleleforge.types.sequence import (
    CoordinateSystem,
    DNASequence,
    GenomicInterval,
    Strand,
)

_IUPAC = "ACGTRYSWKMBDHVN"
_dna = st.text(alphabet=_IUPAC, min_size=0, max_size=40)


def test_positional_and_keyword_construction_match() -> None:
    assert DNASequence("acgt") == DNASequence(sequence="ACGT")


def test_alphabet_is_uppercased() -> None:
    assert DNASequence("acgt").sequence == "ACGT"


def test_rejects_non_iupac() -> None:
    with pytest.raises(ValueError, match="non-IUPAC"):
        DNASequence("ACGTX")


def test_str_returns_bare_sequence() -> None:
    assert str(DNASequence("ACGTRYN")) == "ACGTRYN"


def test_readme_reverse_complement_example() -> None:
    assert str(DNASequence("ACGTRYN").reverse_complement()) == "NRYACGT"


def test_complement_preserves_order() -> None:
    assert str(DNASequence("ACGT").complement()) == "TGCA"


@given(_dna)
def test_reverse_complement_is_involution(seq: str) -> None:
    s = DNASequence(seq)
    assert s.reverse_complement().reverse_complement() == s


@given(st.text(alphabet="ACGT", min_size=1, max_size=30))
def test_unambiguous_rc_matches_manual(seq: str) -> None:
    table = {"A": "T", "T": "A", "C": "G", "G": "C"}
    manual = "".join(table[b] for b in reversed(seq))
    assert str(DNASequence(seq).reverse_complement()) == manual


def test_is_ambiguous_flag() -> None:
    assert DNASequence("ACGTN").is_ambiguous
    assert not DNASequence("ACGT").is_ambiguous


def test_gc_content() -> None:
    assert DNASequence("GGCC").gc_content() == 1.0
    assert DNASequence("ATAT").gc_content() == 0.0
    assert DNASequence("").gc_content() == 0.0


def test_len_and_indexing_and_slice() -> None:
    s = DNASequence("ACGTACGT")
    assert len(s) == 8
    assert s[0] == DNASequence("A")
    assert s[1:4] == DNASequence("CGT")


def test_strand_opposite() -> None:
    assert Strand.PLUS.opposite() is Strand.MINUS
    assert Strand.MINUS.opposite() is Strand.PLUS


def test_strand_is_str_valued() -> None:
    assert Strand.PLUS.value == "+"


def test_interval_length_and_len() -> None:
    iv = GenomicInterval(chrom="chr1", start=10, end=30, strand=Strand.PLUS)
    assert iv.length == 20
    assert len(iv) == 20


def test_interval_rejects_negative_start() -> None:
    with pytest.raises(ValueError, match="negative"):
        GenomicInterval(chrom="c", start=-1, end=5, strand=Strand.PLUS)


def test_interval_rejects_inverted() -> None:
    with pytest.raises(ValueError, match="precedes"):
        GenomicInterval(chrom="c", start=10, end=5, strand=Strand.PLUS)


def test_to_one_based_roundtrip_semantics() -> None:
    iv = GenomicInterval(chrom="chr1", start=10, end=30, strand=Strand.PLUS)
    one = iv.to_one_based()
    assert one.start == 11
    assert one.end == 30
    assert one.coordinate_system is CoordinateSystem.ONE_BASED
    assert one.length == iv.length


def test_to_one_based_rejects_double_conversion() -> None:
    iv = GenomicInterval(
        chrom="c",
        start=10,
        end=30,
        strand=Strand.PLUS,
        coordinate_system=CoordinateSystem.ONE_BASED,
    )
    with pytest.raises(ValueError, match="already 1-based"):
        iv.to_one_based()


def test_overlaps() -> None:
    a = GenomicInterval(chrom="c", start=0, end=10, strand=Strand.PLUS)
    b = GenomicInterval(chrom="c", start=5, end=15, strand=Strand.PLUS)
    c = GenomicInterval(chrom="c", start=10, end=20, strand=Strand.PLUS)
    d = GenomicInterval(chrom="other", start=0, end=10, strand=Strand.PLUS)
    assert a.overlaps(b)
    assert not a.overlaps(c)  # half-open: [0,10) and [10,20) do not overlap
    assert not a.overlaps(d)
