"""A donor built without a guide has no re-cut disposition, and must not be given one.

``hdr_donor`` accepts no guide — a caller who wants the repair template alone need not
have chosen one yet — and in that case it cannot say whether the repaired allele is
still a Cas9 substrate: there is no guide to re-cut it. Its own note said exactly that
("re-cut disposition not assessed"), but ``recut_blocked`` is the field every consumer
reads, and it was ``False``. Falsy reads as *assessed and not blocked*, so the ordering
sheet told the user, as fact, that "the repaired product is still a substrate for this
guide (no PAM-blocking mutation was available)" — two claims about a guide that was
never supplied and a search that was never run. The prose carried the honest third
state and every machine surface collapsed it.
"""

from __future__ import annotations

from collections.abc import Callable

from alleleforge.enumerate.cas9 import hdr_donor
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.report.oligos import donor_oligo
from alleleforge.types.edit import EditIntent
from alleleforge.variant.resolver import ResolvedVariant

from .conftest import PAD, SPACER
from .test_cas9 import _resolve_at

MakeRef = Callable[[dict[str, str]], ReferenceGenome]


def _unassessed(make_reference: MakeRef) -> tuple[ResolvedVariant, ReferenceGenome]:
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    return _resolve_at(ref, "chr2", 32), ref


def test_an_unguided_donor_reports_no_disposition(make_reference: MakeRef) -> None:
    rv, ref = _unassessed(make_reference)
    donor = hdr_donor(rv, EditIntent.CORRECT, reference=ref, arm_length=5, guide=None)
    assert donor is not None
    assert donor.recut_blocked is None, "no guide was supplied, so nothing was assessed"
    assert donor.note is not None and "not assessed" in donor.note


def test_the_ordering_sheet_does_not_invent_a_failed_search(make_reference: MakeRef) -> None:
    rv, ref = _unassessed(make_reference)
    donor = hdr_donor(rv, EditIntent.CORRECT, reference=ref, arm_length=5, guide=None)
    assert donor is not None
    warnings = " ".join(donor_oligo(donor).warnings)
    assert "no PAM-blocking mutation was available" not in warnings, (
        "no search was run; the sheet must not report its outcome"
    )
    assert "still a substrate for this guide" not in warnings, "there is no guide"
    assert "not assessed" in warnings, "the unknown must reach the ordering boundary"


def test_an_assessed_unblocked_donor_still_gets_the_definite_warning(
    make_reference: MakeRef,
) -> None:
    """The negative case: with a guide, the search really did run and fail."""
    from alleleforge.enumerate.cas9 import enumerate_cas9

    rv, ref = _unassessed(make_reference)
    guides = enumerate_cas9(rv, EditIntent.CORRECT, reference=ref, actionable_radius=10)
    assert guides, "fixture must yield a guide, or this test measures nothing"
    donor = hdr_donor(rv, EditIntent.CORRECT, reference=ref, guide=guides[0])
    assert donor is not None
    assert donor.recut_blocked is not None, "a guide was supplied, so it was assessed"
    warnings = " ".join(donor_oligo(donor).warnings)
    if donor.recut_blocked is False:
        assert "no PAM-blocking mutation was available" in warnings
    assert "not assessed" not in warnings
