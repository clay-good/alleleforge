"""A message about an off-by-one printed two conventions under one set of digits.

`chrom:pos:ref>alt` is read as a **1-based** VCF record and printed with a **0-based**
position, and the refusal for a reference mismatch reports the position the printed way
while suggesting an input the read way. When the asserted ref sits one base *right* the
message spells all of that out — it is the "this tool does not accept its own printed
variant" case, and it has a round of its own. When it sits one base *left* the message
was:

    reference mismatch at chr1:15000: asserted ref 'C' but reference has 'G'
      — the asserted ref is one base left; try chr1:15000:C>A

"Position 15000 is wrong; try position 15000." The two numbers are the same digits in
different conventions, printed side by side, in the one message whose whole subject is a
coordinate being off by one.

Both branches now state the convention, and both suggestions are checked by *running
them*: a remedy that does not resolve is worse than no remedy.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.variant.resolver import resolve


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    rng = random.Random(19)
    sequence = "".join(rng.choice("ACGT") for _ in range(2_000))
    fasta = tmp_path / "chr1.fa"
    fasta.write_text(f">chr1\n{sequence}\n")
    return ReferenceGenome(fasta, build="hg38")


def _bases(reference: ReferenceGenome) -> str:
    return "".join(Path(reference.path).read_text().split("\n")[1:])


def _refusal(variant: str, reference: ReferenceGenome) -> str:
    with pytest.raises(ValueError) as caught:
        resolve(variant, reference=reference)
    return str(caught.value)


def _suggested(message: str) -> str:
    """Return the variant the message tells the caller to try."""
    assert "; try " in message, message
    return message.rsplit("; try ", 1)[1].strip()


def test_the_input_convention_is_one_based(reference: ReferenceGenome) -> None:
    """The premise every check below rests on."""
    bases = _bases(reference)
    resolved = resolve(f"chr1:1000:{bases[999]}>A", reference=reference)
    assert resolved is not None


@pytest.mark.parametrize("offset,side", [(1, "right"), (-1, "left")])
def test_both_directions_state_the_convention(
    reference: ReferenceGenome, offset: int, side: str
) -> None:
    bases = _bases(reference)
    # A position whose neighbour on `side` carries the asserted ref, and whose own base
    # does not — so the refusal is the off-by-one one and not a plain mismatch.
    for index in range(1000, 1500):
        wanted, actual = bases[index + offset], bases[index]
        if wanted != actual:
            break
    else:  # pragma: no cover - a 500-base run of one base is not a real reference
        pytest.fail("no usable locus in the fixture")

    message = _refusal(f"chr1:{index + 1}:{wanted}>A", reference)
    assert "1-based" in message, (side, message)
    assert "0-based" in message, (side, message)
    assert f"one base {side}" in message, (side, message)


@pytest.mark.parametrize("offset", [1, -1])
def test_the_remedy_it_names_actually_resolves(reference: ReferenceGenome, offset: int) -> None:
    """The point of a remedy. Both branches suggest an input, and both must work."""
    bases = _bases(reference)
    for index in range(1000, 1500):
        wanted, actual = bases[index + offset], bases[index]
        if wanted != actual:
            break
    else:  # pragma: no cover
        pytest.fail("no usable locus in the fixture")

    message = _refusal(f"chr1:{index + 1}:{wanted}>A", reference)
    resolved = resolve(_suggested(message), reference=reference)
    assert resolved is not None, message
    # And it is the locus the caller meant: the base they asserted, where it really is.
    assert str(resolved.variant.ref) == wanted, (message, resolved.variant)


@pytest.mark.parametrize("offset,side", [(1, "right"), (-1, "left")])
def test_a_deletions_remedy_spells_out_its_empty_alt(
    reference: ReferenceGenome, offset: int, side: str
) -> None:
    """A deletion has no alt, and an alt that prints as nothing is not a remedy.

    Both branches end on ``{variant.alt or '-'}``, and the fallback had no case: every
    fixture here asserts ``>A``, so the ``or '-'`` arm could be dropped with the suite
    green. Drop it and a deletion's suggestion is printed as ``chr1:1000:C>`` — the alt
    is simply absent, which reads as a message cut off mid-word rather than as "this
    deletes the C". The resolver happens to parse that truncated form too, so "run the
    remedy and see that it resolves" cannot see the difference either; only the printed
    dash can.
    """
    bases = _bases(reference)
    for index in range(1000, 1500):
        wanted, actual = bases[index + offset], bases[index]
        if wanted != actual:
            break
    else:  # pragma: no cover - a 500-base run of one base is not a real reference
        pytest.fail("no usable locus in the fixture")

    message = _refusal(f"chr1:{index + 1}:{wanted}>", reference)
    assert f"one base {side}" in message, (side, message)
    suggestion = _suggested(message)
    assert suggestion.endswith(f":{wanted}>-"), (side, message)
    # And the dash is a form this tool reads back, deleting the base they asserted:
    # the resolved deletion is re-anchored, so its ref is the anchor plus that base.
    resolved = resolve(suggestion, reference=reference)
    assert str(resolved.variant.ref) == str(resolved.variant.alt) + wanted, (
        message,
        resolved.variant,
    )
