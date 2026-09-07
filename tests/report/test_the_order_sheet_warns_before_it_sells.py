"""The printable order sheet buried its hazards and printed half of them twice.

`oligo_lines` builds the block a bench scientist orders from. It read, in order:

    cloning oligos (px330-bbsi, BbsI):
      top    5'-CACCGCCTGAAGACTTACGCATACT-3'
      bottom 5'-AAACAGTATGCGTAAGTCTTCAGGC-3'
      note: a 5' G was prepended ...
      WARNING: internal-BbsI-site:sgrna:+@8
      prep: Phosphorylate the annealed oligos ...

The warning says the enzyme that assembles this construct also cuts it — do not order
this insert — and it sat *below* the two lines a person copies into a vendor form, in the
same indent as the U6 note and the ligation prep. A reader who has what they came for
stops reading.

A precise nuclease candidate was worse. Its donor's hazards are promoted into the guide's
warning list so one place carries everything, and the donor block *also* printed them, so
each appeared twice — `WARNING - ...` and `WARNING: ...`, differing by one character of
punctuation. Someone counting hazards on the sheet counted four where there were two, and
had to read two long sentences to the end to find out.

The promotion is now prefixed, which is what `SgRnaOligos.warnings` already claimed it
was: consolidated with the guide's own hazards, "is 250 nt, beyond what most vendors
synthesize" does not say which of the two reagents is too long — and in the flat table's
`oligo_warnings` column there is no other column to say it either.
"""

from __future__ import annotations

import pytest

from alleleforge.report.oligos import (
    DONOR_WARNING_PREFIX,
    LENTIGUIDE_BSMBI,
    SgRnaOligos,
    donor_oligo,
    sgrna_oligos,
)
from alleleforge.report.pdf import oligo_lines
from alleleforge.types.guide import HDRDonor
from alleleforge.types.sequence import DNASequence

#: A spacer carrying BsmBI's own site, so the block really does have a hazard on it.
_HAZARDOUS_SPACER = "GCGTCTCTTACCGTACGTAC"


@pytest.fixture
def hazardous() -> SgRnaOligos:
    oligos = sgrna_oligos(_HAZARDOUS_SPACER, scheme=LENTIGUIDE_BSMBI, kind="sgrna")
    assert oligos.warnings, "the fixture no longer trips the screen"
    return oligos


@pytest.fixture
def with_donor(hazardous: SgRnaOligos) -> SgRnaOligos:
    """A guide plus an over-long, re-cuttable donor — two hazards from two reagents."""
    donor = donor_oligo(HDRDonor(sequence=DNASequence(sequence="A" * 250), recut_blocked=False))
    assert len(donor.warnings) == 2, donor.warnings
    promoted = tuple(f"{DONOR_WARNING_PREFIX}{w}" for w in donor.warnings)
    return hazardous.model_copy(update={"donor": donor, "warnings": hazardous.warnings + promoted})


def _index_of(lines: list[str], needle: str) -> int:
    for i, line in enumerate(lines):
        if needle in line:
            return i
    raise AssertionError(f"{needle!r} not on the sheet:\n" + "\n".join(lines))


def test_the_hazard_comes_before_the_sequence_to_order(hazardous: SgRnaOligos) -> None:
    lines = oligo_lines(hazardous)
    assert _index_of(lines, "WARNING") < _index_of(lines, "top    5'-"), "\n".join(lines)


def test_the_hazard_still_comes_after_the_block_it_belongs_to(hazardous: SgRnaOligos) -> None:
    """Above the sequences, not above the header — it must stay attached to its block."""
    lines = oligo_lines(hazardous)
    assert _index_of(lines, "cloning oligos (") < _index_of(lines, "WARNING")


def test_each_hazard_is_printed_exactly_once(with_donor: SgRnaOligos) -> None:
    lines = oligo_lines(with_donor)
    warnings = [line for line in lines if "WARNING" in line]
    # Long messages wrap, so count the marker rather than the lines.
    assert sum(line.count("WARNING") for line in warnings) == len(with_donor.warnings), "\n".join(
        lines
    )


def test_the_two_punctuations_are_gone(with_donor: SgRnaOligos) -> None:
    """`WARNING - x` and `WARNING: x` on one sheet read as two different hazards."""
    sheet = "\n".join(oligo_lines(with_donor))
    assert "WARNING - " not in sheet, sheet


def test_a_donor_hazard_says_it_is_the_donors(with_donor: SgRnaOligos) -> None:
    promoted = [w for w in with_donor.warnings if w.startswith(DONOR_WARNING_PREFIX)]
    assert len(promoted) == 2, with_donor.warnings
    guide_hazards = [w for w in with_donor.warnings if not w.startswith(DONOR_WARNING_PREFIX)]
    assert guide_hazards, "the guide's own hazard was swallowed by the prefixing"


def test_a_guide_with_no_donor_keeps_its_warnings_unprefixed(hazardous: SgRnaOligos) -> None:
    assert not any(w.startswith(DONOR_WARNING_PREFIX) for w in hazardous.warnings)
