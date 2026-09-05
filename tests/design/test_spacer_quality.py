"""Pol III spacer caveats apply to every chemistry, not just prime editing.

Found by running a base-editor design and reading the card. The top-ranked candidate,
marked `recommended`, carried a spacer with **5% GC** — outside the band where U6
transcription and oligo synthesis behave — and was reported `clean` with no caveat.
The identical spacer inside a pegRNA would have been flagged: the check lived in the
prime vertical only, so the same physical problem was surfaced on one chemistry of
three.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from alleleforge.design.spacer_quality import GC_BAND, spacer_quality_flags
from alleleforge.genome.reference import ReferenceGenome

MakeRef = Callable[[dict[str, str]], ReferenceGenome]


def test_the_checks_themselves() -> None:
    assert spacer_quality_flags("GACGTACGTACGTACGTACG") == []  # 5' G, GC 0.50 in band
    assert spacer_quality_flags("ACGTACGTACGTACGTACGT") == ["no-5prime-g"]
    assert spacer_quality_flags("TTTTTATTTTTTTTTTTTTT") == ["no-5prime-g", "gc-out-of-band:0.00"]
    assert spacer_quality_flags("GGGGGGGGGGGGGGGGGGGG") == ["gc-out-of-band:1.00"]
    assert spacer_quality_flags("") == []  # no spacer, no claim
    # The band is a band, not a floor: both edges are exercised above.
    assert GC_BAND[0] < GC_BAND[1]


@pytest.mark.parametrize(
    ("intent", "expected_chemistry"),
    [("install", "base_abe"), ("knock_out", "cas9_nuclease")],
)
def test_every_chemistry_flags_a_bad_spacer(
    make_reference: MakeRef, intent: str, expected_chemistry: str
) -> None:
    """A 5% GC spacer is a bad reagent whichever chemistry is holding it."""
    from alleleforge.design.designer import design
    from alleleforge.types.edit import EditIntent

    # A protospacer of almost pure T, with an NGG PAM: enumerable, and a poor reagent.
    contig = "ACGT" * 125 + "TTTTTATTTTTTTTTTTTTT" + "TGG" + "ACGT" * 125
    reference = make_reference({"chr1": contig})
    menu = design(
        "chr1:506:A>G",
        intent=EditIntent(intent),
        reference=reference,
        run_offtarget=False,
    )
    matching = [c for c in menu.candidates if c.chemistry.value == expected_chemistry]
    assert matching, f"fixture produced no {expected_chemistry} candidate"
    assert any("gc-out-of-band" in flag for flag in matching[0].flags), (
        f"{expected_chemistry} spacer {matching[0].flags}"
    )
