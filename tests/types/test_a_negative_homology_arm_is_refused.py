"""A negative 5' homology arm would inflate the edit length the menu publishes.

`PegRNA.templated_edit_length` is `len(rtt) - rtt_homology_5prime -
rtt_homology_3prime`, and the prime vertical puts that number on the menu as
`templated-edit:Nnt` — a flag that exists because "a menu that shows only geometry hides
whether a candidate installs a single base or a 29-nt insertion: the same numbers, very
different reagents at the bench".

`rtt_homology_5prime` is a plain `int` with no `ge=0` constraint, so a negative is
constructible by any library caller, and subtracting it *adds* to the published edit
length. The geometry validator refuses it — and nothing pinned that refusal, so the
mutation that deletes it survived the suite. The arms-sum check two lines below does not
cover it either: a negative makes the sum smaller, not larger, so it sails through.

The asymmetry is what makes this worth a test rather than a shrug.
`scoring/prime_efficiency.py` already writes `max(0, pegrna.rtt_homology_5prime)`, so a
negative was anticipated on the scoring path and clamped there. The number a person
*orders from* had no such protection, and the enumerator only avoids it by construction
(`distance` is a loop bound), which is a property of today's caller rather than of the
type.

Found by deleting the refusal (`scripts/mutate.py --mode raise`); it survived both the
package list and a broad confirmation.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from alleleforge.types.guide import (
    MIN_RTT_3PRIME_HOMOLOGY,
    PegRNA,
    Spacer,
    ThreePrimeMotif,
)
from alleleforge.types.sequence import DNASequence

_SCAFFOLD = "GTTTTAGAGCTAGAAATAGCAAGTTAAAATAAGGCTAGTCCGTTATCAACTTGAAAAAGTGGCACCGAGTCGGTGC"
_SPACER = "ACGTAACGTTACGTAACGTT"


def _pegrna(*, homology_5prime: int, rtt: str = "ACGTACGTACGTACGT") -> PegRNA:
    return PegRNA(
        spacer=Spacer(sequence=DNASequence(_SPACER)),
        scaffold=DNASequence(_SCAFFOLD),
        rtt=DNASequence(rtt),
        pbs=DNASequence("ACGTACGTACGTA"),
        three_prime_motif=ThreePrimeMotif.TEVOPREQ1,
        rtt_homology_5prime=homology_5prime,
        rtt_homology_3prime=MIN_RTT_3PRIME_HOMOLOGY,
    )


def test_a_zero_homology_arm_is_accepted() -> None:
    """The premise, and the case the guard must NOT fire on.

    Zero is the field's default, so a guard that rejected it would break every pegRNA.
    Without this, the refusal below could pass against an over-eager validator.
    """
    pegrna = _pegrna(homology_5prime=0)
    assert pegrna.rtt_homology_5prime == 0
    assert pegrna.templated_edit_length == len(pegrna.rtt) - MIN_RTT_3PRIME_HOMOLOGY


@pytest.mark.parametrize("negative", [-1, -5, -16])
def test_a_negative_homology_arm_is_refused(negative: int) -> None:
    """Refused at construction, so no downstream surface has to defend against it."""
    with pytest.raises(ValidationError, match="negative"):
        _pegrna(homology_5prime=negative)


def test_the_refusal_is_what_keeps_the_published_edit_length_honest() -> None:
    """Name the consequence, so the test is not read as pedantry about a sign.

    `templated_edit_length` subtracts the arm, so a negative one *adds* to it. The menu
    prints that number as `templated-edit:Nnt`, which is what distinguishes a candidate
    installing a single base from one installing a long insertion — a different reagent
    at the bench, ordered from this figure.
    """
    rtt = "ACGTACGTACGTACGT"
    with pytest.raises(ValidationError):
        _pegrna(homology_5prime=-4, rtt=rtt)

    honest = len(rtt) - 0 - MIN_RTT_3PRIME_HOMOLOGY
    inflated = len(rtt) - (-4) - MIN_RTT_3PRIME_HOMOLOGY
    assert inflated > honest, (
        "a negative arm no longer overstates the templated edit length; the inflation "
        "this guard prevents has changed shape, so rewrite the test rather than delete it"
    )
    assert inflated - honest == 4, (inflated, honest)


def test_the_arms_sum_check_does_not_cover_the_negative_case() -> None:
    """Why the two validators are both needed.

    The sibling check refuses `5' + 3' > len(rtt)`. A negative 5' arm makes that sum
    *smaller*, so it passes — which is precisely why deleting the negative check was
    invisible to the suite.
    """
    rtt = "ACGTACGTACGTACGT"
    assert (-4) + MIN_RTT_3PRIME_HOMOLOGY <= len(rtt), (
        "the arms-sum check would have caught this on its own, making the negative "
        "guard redundant; re-derive which guard is load-bearing"
    )
