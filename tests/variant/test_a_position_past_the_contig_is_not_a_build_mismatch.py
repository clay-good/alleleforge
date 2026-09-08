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
