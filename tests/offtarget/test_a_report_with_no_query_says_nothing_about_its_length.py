"""Each arm of the report's two-part guards, where only one arm was ever exercised.

A conjunct-removal sweep over `types/offtarget.py` left one operand of several guards
unkilled, all for the same reason: every fixture satisfied both arms at once, so dropping
either changed nothing.

* `if self.spacer and not low <= len(self.spacer) <= high` — the guard-length note. Every
  fixture has a spacer, so the `self.spacer` arm never mattered. Drop it and a report with
  **no** spacer is measured anyway: `not 17 <= 0 <= 24` is true, so a report that never
  carried a query would be told its query is the wrong length. The same condition appears
  twice, on the report and in `headline_notes`, and both had the same hole.
* `if searched_bases == 0 and sites == ()` — "NO SEQUENCE WAS SEARCHED". The empty-handed
  case (bases searched, nothing found) was pinned in round 649; the contradictory one
  (nothing searched, yet sites present) was not, so the `sites == ()` arm was free.
* `if mismatches < 0 or dna_bulges < 0 or rna_bulges < 0` on a site — three counts, one
  validator, and only one of them had a fixture.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from alleleforge.types.offtarget import (
    OffTargetReport,
    OffTargetSite,
    ScoreMethod,
    headline_notes,
)
from alleleforge.types.sequence import GenomicInterval, Strand

_LOCUS = GenomicInterval(chrom="chr1", start=10, end=30, strand=Strand.PLUS)


def _report(**kw: object) -> OffTargetReport:
    base: dict[str, object] = {"spacer": "A" * 20, "pam": "NGG"}
    base.update(kw)
    return OffTargetReport(**base)  # type: ignore[arg-type]


def _site() -> OffTargetSite:
    return OffTargetSite(locus=_LOCUS, mismatches=2, score=0.5, score_method=ScoreMethod.CFD)


# --- the guard-length note needs a query to be about ------------------------------


def test_a_report_with_no_spacer_is_not_told_its_query_is_the_wrong_length() -> None:
    report = _report(spacer="", searched_bases=1_000, resolved_bases=1_000)
    assert report.spacer == "", "the fixture must have no query, or this is vacuous"
    assert "not a guide length" not in " ".join(headline_notes(report))
    assert "sequence search" not in report.search_description(), (
        "there is no query here to call a sequence rather than a guide"
    )


def test_a_report_with_a_short_query_is_still_told_so() -> None:
    """The negative case: the length check must still fire when there IS a query."""
    report = _report(spacer="A" * 4, searched_bases=1_000, resolved_bases=1_000)
    assert "sequence search" in report.search_description()


# --- "nothing was searched" means nothing was searched ----------------------------


def test_a_search_that_found_sites_is_never_called_empty() -> None:
    """Contradictory but constructible: zero bases recorded, yet sites present.

    The note exists to stop an empty result reading as a clean one. A result holding
    sites is not an empty result whatever the counter says, and announcing that
    nothing was searched over a list of real hits is the more dangerous error.
    """
    report = _report(searched_bases=0, resolved_bases=0, sites=(_site(),))
    assert report.sites, "the fixture must carry a site, or this measures nothing"
    assert "NO SEQUENCE WAS SEARCHED" not in report.search_description()


def test_a_search_of_nothing_that_found_nothing_is_still_called_empty() -> None:
    """The other arm, so neither can carry this pair alone."""
    report = _report(searched_bases=0, resolved_bases=0)
    assert "NO SEQUENCE WAS SEARCHED" in report.search_description()


# --- every budget is validated, not just the first --------------------------------


def _site_with(**kw: object) -> OffTargetSite:
    base: dict[str, object] = {
        "locus": _LOCUS,
        "mismatches": 2,
        "score": 0.5,
        "score_method": ScoreMethod.CFD,
    }
    base.update(kw)
    return OffTargetSite(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["mismatches", "dna_bulges", "rna_bulges"])
def test_each_mismatch_or_bulge_count_refuses_a_negative_value(field: str) -> None:
    with pytest.raises(ValidationError, match="non-negative"):
        _site_with(**{field: -1})


@pytest.mark.parametrize("field", ["mismatches", "dna_bulges", "rna_bulges"])
def test_each_mismatch_or_bulge_count_accepts_zero(field: str) -> None:
    """Zero is legal — the boundary the refusal must not swallow."""
    assert getattr(_site_with(**{field: 0}), field) == 0


def test_the_headline_notes_never_call_a_result_with_sites_empty() -> None:
    """The same guard as `search_description`, in the module-level notes function.

    Two copies of one rule, and both had the `sites == ()` arm unexercised.
    """
    report = _report(searched_bases=0, resolved_bases=0, sites=(_site(),))
    assert "NO SEQUENCE WAS SEARCHED" not in " ".join(headline_notes(report))


def test_the_headline_notes_do_call_a_truly_empty_result_empty() -> None:
    report = _report(searched_bases=0, resolved_bases=0)
    assert any("NO SEQUENCE WAS SEARCHED" in note for note in headline_notes(report))
