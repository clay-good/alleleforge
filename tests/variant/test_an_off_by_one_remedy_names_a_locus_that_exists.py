"""The off-by-one remedy is measured against the contig, not against its padding.

``_ref_matches_at`` decides whether the asserted ref sits one base away, and it asks two
things of the fetch it makes: that the reference really held those bases
(``not result.padded``) **and** that they equal the assertion. Every fixture in the suite
asks about a locus in the middle of a contig, where no fetch is padded, so the two arms
always agreed and the padding arm was never the one deciding.

A fetch past the end of a contig comes back padded with ``N``. An assembly-gap record —
``N`` in the **ref**, which this project accepts and documents — sitting at the last base
of a contig therefore *matches its own padding* one base to the right. Without the padding
arm the refusal gains a remedy reading "the asserted ref is at chr2:32, one base right"
for a thirty-base contig: a locus that does not exist, offered to a caller whose real
problem is a reference mismatch, under a message this project wrote precisely so that a
wrong remedy would not send a reader somewhere there is nothing to find.

The mirror direction needs no arm of its own: ``pos < 0`` is refused before the fetch.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.variant.resolver import resolve

_SEQ = "TTTTTACGTACGTCAAAGTTGGCCAATTGG"  # 30 bases; last two are 'GG'


@pytest.fixture
def chr2(tmp_path: Path) -> ReferenceGenome:
    fasta = tmp_path / "tiny.fa"
    fasta.write_text(f">chr2\n{_SEQ}\n")
    return ReferenceGenome(fasta, build="hg38")


def test_the_padding_past_the_contig_is_n(chr2: ReferenceGenome) -> None:
    """The premise: without this the cases below prove nothing."""
    result = chr2.fetch_result(
        GenomicInterval(chrom="chr2", start=len(_SEQ) - 1, end=len(_SEQ) + 1, strand=Strand.PLUS)
    )
    assert result.padded
    assert str(result.sequence) == _SEQ[-1] + "N"


@pytest.mark.parametrize(
    "one_based,ref",
    [
        (len(_SEQ), "N"),  # the whole assertion would match pure padding
        (len(_SEQ) - 1, "GN"),  # a real base plus padding, which is the likelier record
    ],
)
def test_an_assertion_matching_only_padding_is_not_an_off_by_one(
    chr2: ReferenceGenome, one_based: int, ref: str
) -> None:
    with pytest.raises(ValueError) as caught:
        resolve(f"chr2:{one_based}:{ref}>A", reference=chr2)
    message = str(caught.value)
    assert "reference mismatch" in message, message
    # No remedy at all is the right answer here, and the message says so.
    assert "one base right" not in message, message
    assert "; try " not in message, message
    assert "(wrong build?)" in message, message


def test_a_real_off_by_one_inside_the_contig_still_gets_its_remedy(
    chr2: ReferenceGenome,
) -> None:
    """The other case, so the test above is not passing by refusing everything."""
    assert _SEQ[12] == "T" and _SEQ[13] == "C"
    with pytest.raises(ValueError) as caught:
        resolve("chr2:13:C>A", reference=chr2)
    assert "one base right" in str(caught.value)
