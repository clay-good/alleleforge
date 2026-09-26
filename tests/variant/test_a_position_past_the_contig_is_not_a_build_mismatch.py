"""A coordinate the contig never had is not an assembly disagreement.

`fetch_result` pads an over-run with `N` so a window near a telomere still comes
back full length. `_validate_ref` folded that padding into the mismatch branch and
reported it as an observation, so a position past the end of a chromosome printed
`asserted ref 'A' but reference has 'N' (wrong build?)` — which sends the reader
to liftover for a variant no assembly conversion can rescue. The real fault is a
truncated or chromosome-only FASTA, or a position pasted in the wrong convention.

The off-target engine already had this right from the other input: a region past a
contig end reports what fraction of the requested bases were searchable and names
"past a contig end" as one of the reasons. The resolver was the outlier.
"""

from __future__ import annotations

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.variant.resolver import resolve

from .conftest import CHR2_SEQ

_LENGTH = len(CHR2_SEQ)


def test_the_fixture_is_short_enough_to_run_off(reference: ReferenceGenome) -> None:
    """Vacuity floor: the positions below really are past the end."""
    assert reference.contig_length("chr2") == _LENGTH
    assert _LENGTH < 100


@pytest.mark.parametrize("beyond", [_LENGTH + 1, _LENGTH + 50, _LENGTH * 3])
def test_a_position_past_the_end_says_so(reference: ReferenceGenome, beyond: int) -> None:
    with pytest.raises(ValueError) as excinfo:
        resolve(f"chr2:{beyond}:A>T", reference=reference)
    message = str(excinfo.value)
    assert "past the end of chr2" in message, message
    assert str(_LENGTH) in message, message
    assert "wrong build" not in message, message
    assert "'N'" not in message, message


def test_a_ref_span_that_runs_off_the_end_says_so(reference: ReferenceGenome) -> None:
    """The last base is real; the span still leaves the contig."""
    # 1-based input for the final base, with a 3 nt asserted ref.
    with pytest.raises(ValueError) as excinfo:
        resolve(f"chr2:{_LENGTH}:{CHR2_SEQ[-1]}AA>T", reference=reference)
    assert "past the end of chr2" in str(excinfo.value), excinfo.value


def test_a_real_mismatch_inside_the_contig_still_blames_the_build(
    reference: ReferenceGenome,
) -> None:
    """The new branch must not swallow the case it sits in front of."""
    wrong = "G" if CHR2_SEQ[5] != "G" else "C"
    with pytest.raises(ValueError) as excinfo:
        resolve(f"chr2:6:{wrong}>T", reference=reference)
    message = str(excinfo.value)
    assert "reference mismatch" in message, message
    assert "past the end" not in message, message


def test_the_last_base_of_the_contig_still_resolves(reference: ReferenceGenome) -> None:
    """Guard the boundary from the inside: off-by-one here would refuse real input."""
    resolved = resolve(f"chr2:{_LENGTH}:{CHR2_SEQ[-1]}>A", reference=reference)
    assert resolved.variant.pos == _LENGTH - 1


# -- the numbers inside the refusal ---------------------------------------------
#
# This message is a specification: it is the only place a caller is told what range the
# contig actually has, and it is what they will use to fix their input. Mutation sweeps
# left three of its numbers unpinned — the last valid position, the span's end, and
# whether the span is rendered as a point or a range — because every existing assertion
# checks that the message *mentions* the length, not that its arithmetic is right.


def test_the_refusal_names_the_last_valid_position(reference: ReferenceGenome) -> None:
    """`0-based positions 0-{length - 1}`, which is the number the caller will reuse.

    Off by one and the message invites exactly the position it is refusing: a caller told
    the range ends at `length` will try `length`, be refused again, and have no way to tell
    which of the two numbers was wrong.
    """
    with pytest.raises(ValueError) as excinfo:
        resolve(f"chr2:{_LENGTH + 5}:A>T", reference=reference)
    message = str(excinfo.value)

    assert f"0-based positions 0-{_LENGTH - 1}" in message, message
    assert f"positions 0-{_LENGTH}" not in message, message


def test_a_single_base_refusal_names_a_position_and_a_span_names_a_range(
    reference: ReferenceGenome,
) -> None:
    """`span = pos if len(ref) == 1 else f"{pos}-{end}"`, and `end = pos + len(ref)`.

    Inverting the length test prints a one-base variant as a range and a multi-base one as
    a point; mis-signing the end prints a range that runs backwards. Either way the
    coordinates in the refusal are not the coordinates the caller sent.
    """
    with pytest.raises(ValueError) as single:
        resolve(f"chr2:{_LENGTH + 5}:A>T", reference=reference)
    assert f"variant at chr2:{_LENGTH + 4} lies past the end" in str(single.value), single.value

    # A four-base ref anchored one before the end: the span must read start-to-end.
    with pytest.raises(ValueError) as span:
        resolve(f"chr2:{_LENGTH - 1}:AAAA>A", reference=reference)
    start = _LENGTH - 2  # the input is 1-based; the message prints 0-based
    assert f"variant at chr2:{start}-{start + 4} lies past the end" in str(span.value), span.value
