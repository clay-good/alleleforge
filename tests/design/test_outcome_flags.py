"""`P(intended)` had no caveat at any value.

It is the number a reader is actually deciding on — of everything this reagent
produces, how much is the edit that was asked for. A real report printed
`P(intended) = 0.05` beside an outcome table whose most likely row was a
bystander-only edit at 0.288, and the CAVEATS block said nothing about it.

The flag is deliberately not a threshold. "Low" needs a number nobody can defend; the
honest statement is a comparison the data already makes — whether the single most
likely outcome is the requested edit.
"""

from __future__ import annotations

import pytest

from alleleforge.design.outcome_flags import outcome_flags
from alleleforge.types.edit import AlleleOutcome, EditOutcome


def _outcome(*pairs: tuple[str, float, bool]) -> EditOutcome:
    return EditOutcome(
        alleles=tuple(
            AlleleOutcome(allele=name, probability=p, is_intended=intended)
            for name, p, intended in pairs
        )
    )


def test_a_non_modal_intended_outcome_is_flagged() -> None:
    """The case from the real report: a bystander-only edit beats the requested one."""
    # The real distribution, renormalised: EditOutcome requires the alleles to sum
    # to ~1.0, which is its own contract and worth respecting in a fixture.
    flags = outcome_flags(
        _outcome(("A6G", 0.55, False), ("wildtype", 0.36, False), ("A4G", 0.09, True))
    )
    assert flags == ["intended-not-modal:0.09"]


def test_a_modal_intended_outcome_is_not_flagged() -> None:
    flags = outcome_flags(_outcome(("A4G", 0.7, True), ("wildtype", 0.3, False)))
    assert flags == []


def test_no_intended_allele_raises_nothing() -> None:
    """The NHEJ-spectrum case, which has its own flag; this must not double up."""
    assert outcome_flags(_outcome(("+1", 0.6, False), ("-2", 0.4, False))) == []
    assert outcome_flags(None) == []


def test_the_flag_carries_the_probability_not_a_verdict() -> None:
    """A reader judges the size of the gap; the flag does not judge it for them."""
    flags = outcome_flags(_outcome(("x", 0.51, False), ("wanted", 0.49, True)))
    assert flags == ["intended-not-modal:0.49"]


def test_the_caveat_is_classified() -> None:
    from alleleforge.report.builder import caveats

    found = dict(caveats(("intended-not-modal:0.05",)))
    assert found, "the flag produced no caveat"
    assert "not the requested edit" in next(iter(found.values()))


@pytest.mark.parametrize("vertical", ["cas9", "prime", "base_editor"])
def test_every_vertical_derives_it(vertical: str) -> None:
    """Two rounds running, a flag was missing from a vertical because its `_flags`
    was never passed the data — the off-target report, then the outcome."""
    import inspect

    from alleleforge.design import base_editor, cas9, prime

    module = {"cas9": cas9, "prime": prime, "base_editor": base_editor}[vertical]
    assert "outcome_flags(" in inspect.getsource(module)
