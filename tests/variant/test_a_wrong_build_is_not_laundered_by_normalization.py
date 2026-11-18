"""`_left_align` refuses a wrong-build anchor on its own, not because its caller does.

`resolve` validates the asserted reference span three times: the raw assertion before
normalization, once inside `_left_align`, and once on the normalized result. A
statement-deletion sweep removed each in turn, and two of the three survived the whole
suite. Triaging them apart is the point of this file, because they are not the same
kind of thing.

**The one inside `_left_align` is a real gap.** The re-anchor step re-reads the anchor
base *from the reference*, so an insertion whose asserted anchor disagrees would have
its assertion overwritten rather than refused — the fail-closed promise inverted,
precisely for insertions. Inside `resolve` the raw check above already stops that, which
is why nothing noticed; but `_left_align` is a function with its own contract and its
own direct callers in this suite, and a guarantee that holds only because of what one
caller happens to do first is not the function's guarantee. It is pinned here at the
function.

**The one after normalization is inert**, and that was measured rather than assumed:
185,640 inputs — every position of the fixture contig crossed with every ref/alt pair up
to three bases, including empty alleles — produced no difference with it removed. Left
alignment builds its new ref out of reference bases, so the result matches by
construction. Recorded so the next sweep does not re-derive it.

The first check, before normalization, already had a test, and the case it exists for is
restated here beside the others because it is the one that makes the ordering matter:
`normalized()` trims a shared prefix or suffix base whenever `ref == alt` there, so an
asserted `AT>GT` over a reference holding `AC` loses the disagreeing `T` and leaves
`A>G`, which validates. A check that runs after that cannot see it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.variant import Variant
from alleleforge.variant.resolver import _left_align, resolve

#: The conftest contig, restated so this file's arithmetic does not move with a fixture.
_SEQ = "TTTTTACGTACGTCAAAGTTGGCCAATTGG"


@pytest.fixture
def chr2(tmp_path: Path) -> ReferenceGenome:
    fasta = tmp_path / "tiny.fa"
    fasta.write_text(f">chr2\n{_SEQ}\n")
    return ReferenceGenome(fasta, build="hg38")


def test_the_fixture_is_the_laundering_case() -> None:
    """0-based 5-6 is `AC`, so an asserted `AT` disagrees only in the trimmed base."""
    assert _SEQ[5:7] == "AC"


def test_a_mismatch_in_a_base_normalization_trims_is_still_a_mismatch(
    chr2: ReferenceGenome,
) -> None:
    """`AT>GT` over `AC`: trimmed to `A>G`, which validates. It must not be accepted."""
    with pytest.raises(ValueError) as caught:
        resolve("chr2:6:AT>GT", reference=chr2)
    message = str(caught.value)
    assert "reference mismatch" in message, message
    assert "'AT'" in message or "AT" in message, message


def test_the_trimmed_form_of_that_same_edit_does_resolve(chr2: ReferenceGenome) -> None:
    """The other side: `A>G` at the same locus is a correct assertion and is accepted.

    Without this, the check above would pass on a resolver that refused everything.
    """
    resolved = resolve("chr2:6:A>G", reference=chr2)
    assert str(resolved.variant.ref) == "A"
    assert resolved.variant.pos == 5


def test_left_align_refuses_an_insertion_whose_anchor_disagrees(
    chr2: ReferenceGenome,
) -> None:
    """The anchor is re-read from the reference, so it has to be checked before that."""
    assert _SEQ[5] == "A", "the fixture's anchor base"
    wrong = Variant(chrom="chr2", pos=5, ref="G", alt="GCC", build="hg38")
    with pytest.raises(ValueError) as caught:
        _left_align(wrong, chr2)
    assert "reference mismatch" in str(caught.value)


def test_left_align_accepts_the_same_insertion_with_the_right_anchor(
    chr2: ReferenceGenome,
) -> None:
    """The negative case, so the refusal above is not a refusal of everything."""
    right = Variant(chrom="chr2", pos=5, ref="A", alt="ACC", build="hg38")
    aligned = _left_align(right, chr2)
    assert aligned.alt.startswith(aligned.ref)
