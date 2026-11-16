"""An absent allele prints as a dash, so the parser has to read a dash.

:meth:`Variant.__str__` renders ``f"{ref or '-'}>{alt or '-'}"``: a deletion comes out
as ``chr1:999:C>-`` and an insertion as ``chr1:999:->CA``. The coordinate pattern read
``[ACGTN]*`` on both sides and nothing else, so every one of those strings came back
``unrecognized variant input`` — the tool refusing its own printed form, which is the
sin the off-by-one remedy in this module exists to explain for *positions*.

It was not only a round-trip nicety. ``_off_by_one_remedy`` builds its suggestion from
the same ``or '-'`` fallback, so the refusal for a mis-conventioned **deletion** ended
``; try chr1:1000:C>-`` — a remedy that could not be run, printed under a message whose
entire job is to hand back a string that works. `test_the_remedy_it_names_actually
_resolves` had run every remedy it was given, but only ever for substitutions, where
both alleles are present and the fallback never fires.

Both spellings are accepted now, and the dash is not a third allele: it means exactly
the empty string, so ``C>`` and ``C>-`` resolve to the same variant.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.variant import Variant
from alleleforge.variant.resolver import parses_as_variant, resolve

#: 0-based 13 = 'C', 14-16 = 'AAA' — the conftest contig, restated so this file's
#: claims do not move when a shared fixture does.
_SEQ = "TTTTTACGTACGTCAAAGTTGGCCAATTGG"


@pytest.fixture
def chr2(tmp_path: Path) -> ReferenceGenome:
    fasta = tmp_path / "tiny.fa"
    fasta.write_text(f">chr2\n{_SEQ}\n")
    return ReferenceGenome(fasta, build="hg38")


@pytest.mark.parametrize(
    "ref,alt",
    [("C", ""), ("", "CA"), ("CA", ""), ("", "G")],
)
def test_the_printed_form_of_an_absent_allele_is_a_dash(ref: str, alt: str) -> None:
    """The premise: this is the string the tool puts in front of a user."""
    printed = str(Variant(chrom="chr2", pos=13, ref=ref, alt=alt))
    assert "-" in printed, printed
    assert printed == f"chr2:13:{ref or '-'}>{alt or '-'}"


@pytest.mark.parametrize("text", ["chr2:14:A>-", "chr2:14:->GG", "chr2:14:AAA>-", "chr2:14:->A"])
def test_a_dash_spelling_is_recognized_as_a_variant(text: str) -> None:
    """Shape only — the routing answer, with no reference and no database."""
    assert parses_as_variant(text)


@pytest.mark.parametrize(
    "dashed,empty", [("chr2:15:A>-", "chr2:15:A>"), ("chr2:14:->G", "chr2:14:>G")]
)
def test_a_dash_means_the_empty_string_and_nothing_else(
    chr2: ReferenceGenome, dashed: str, empty: str
) -> None:
    assert resolve(dashed, reference=chr2).variant == resolve(empty, reference=chr2).variant


def test_a_dash_is_not_a_base(chr2: ReferenceGenome) -> None:
    """It is the absence of one, so it cannot stand next to real bases in an allele."""
    assert not parses_as_variant("chr2:14:A->GG")
    with pytest.raises(ValueError):
        resolve("chr2:14:A->GG", reference=chr2)
