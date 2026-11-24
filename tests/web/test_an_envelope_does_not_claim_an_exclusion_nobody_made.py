"""The off-target envelope could claim the on-target site was excluded when it was not.

`on_target_excluded` is a disclosure on a published API response: it tells a client
whether the guide's own intended cut site was removed from the nominated-site list.
Whoever reads `n_sites` needs it, because the same count means different things depending
on the answer.

`from_report` takes it as `on_target_excluded: bool = False` and every caller passes it,
so flipping the declared default changed no shipped response and the suite stayed green —
even though `tests/web/test_api.py` already builds an envelope *without* the keyword. The
default was exercised and never asserted, which is the difference between a line being
covered and a claim being checked.

The direction is the part worth keeping: the surviving mutation makes the envelope assert
an exclusion that nobody performed. A client trusting it would read a site count as
"off-targets only" when it still includes the on-target cut.

Found by flipping the default (`scripts/mutate.py --mode dflt`).
"""

from __future__ import annotations

from alleleforge.types.offtarget import OffTargetReport, OffTargetSite, ScoreMethod
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.web.api.models import OffTargetResponse


def _report() -> OffTargetReport:
    site = OffTargetSite(
        locus=GenomicInterval(chrom="chr2", start=100, end=120, strand=Strand.PLUS),
        mismatches=2,
        score=0.9,
        score_method=ScoreMethod.CFD,
    )
    return OffTargetReport(spacer="A" * 20, pam="NGG", sites=(site,))


def test_an_envelope_claims_no_exclusion_unless_told() -> None:
    """Omitting the keyword must mean "nothing was excluded"."""
    assert OffTargetResponse.from_report(_report()).on_target_excluded is False, (
        "the envelope claimed the on-target site was excluded without being told it "
        "was; a client would then read n_sites as off-targets only"
    )


def test_an_envelope_reports_an_exclusion_that_was_made() -> None:
    """The other side, so the field is not pinned to a constant."""
    assert (
        OffTargetResponse.from_report(_report(), on_target_excluded=True).on_target_excluded is True
    )
