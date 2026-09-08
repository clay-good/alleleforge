"""A coordinate the caller never typed must not appear in the refusal.

`chrom:pos:ref>alt` is read as a 1-based VCF record and stored 0-based, so
`chr11:0:T>C` reached `Variant` as `pos=-1` and pydantic's field validator answered
with its own machinery: "1 validation error for Variant / pos / Value error, pos -1
is negative [type=value_error, input_value=-1, input_type=int] / For further
information visit https://errors.pydantic.dev/...". Four things wrong with that for
a caller who typed `0` — a number they never wrote, an internal model name, a
framework's formatting, and a link to a library they did not import — sitting beside
a dozen sibling refusals that are one curated sentence.

`0` is also the specific mistake worth catching: it is what pasting a printed
0-based position for the first base of a contig produces.
"""

from __future__ import annotations

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.variant import Variant
from alleleforge.variant.resolver import VcfRecord, resolve


@pytest.mark.parametrize("pos", [0, -1, -5])
def test_a_non_positive_position_is_refused_in_words(reference: ReferenceGenome, pos: int) -> None:
    with pytest.raises(ValueError) as excinfo:
        resolve(f"chr2:{pos}:A>T", reference=reference)
    message = str(excinfo.value)
    assert "1-based" in message, message
    assert "validation error" not in message, message
    assert "pydantic" not in message, message
    # The number in the refusal is the one the caller typed, not the converted one.
    assert str(pos) in message, message
    assert "pos -1" not in message, message


def test_a_vcf_record_gets_the_same_refusal() -> None:
    """The other 1-based entry point; it did the same conversion."""
    with pytest.raises(ValueError) as excinfo:
        VcfRecord(chrom="chr2", pos=0, ref="A", alt="T").to_variant()
    assert "1-based" in str(excinfo.value), excinfo.value


def test_the_first_base_of_a_contig_still_resolves(reference: ReferenceGenome) -> None:
    """The boundary from the inside: position 1 is real input."""
    resolved = resolve("chr2:1:T>A", reference=reference)
    assert resolved.variant.pos == 0


def test_the_model_validator_is_still_the_library_backstop() -> None:
    """A caller who builds a `Variant` directly is still stopped."""
    with pytest.raises(ValueError, match="negative"):
        Variant(chrom="chr2", pos=-1, ref="A", alt="T")
