"""The off-target report's own validation, defaults, and coverage sentence, on their edges.

A constant-mutation sweep of `types/offtarget.py` found:

* the [0, 1] validators on score, MIT score, and frequency never tested at 0 or 1;
* the report's default search budgets free to drift from the engine's and the API's,
  which this project has found more than once to be how two shells end up answering
  one question differently;
* the coverage sentence free to say "NO SEQUENCE WAS SEARCHED" over a clean search that
  found nothing, to divide by zero when nothing was searched, to call a spacer at either
  end of the guide-length range "a sequence search", and to describe an empty
  sub-threshold tail.
"""

from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from alleleforge.offtarget.engine import search
from alleleforge.types.guide import GUIDE_SPACER_RANGE
from alleleforge.types.offtarget import OffTargetReport, OffTargetSite, ScoreMethod
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.web.api.models import OffTargetRequest

_LOCUS = GenomicInterval(chrom="chr1", start=10, end=30, strand=Strand.PLUS)


def _site(**kw: object) -> OffTargetSite:
    base: dict[str, object] = {
        "locus": _LOCUS,
        "mismatches": 2,
        "score": 0.5,
        "score_method": ScoreMethod.CFD,
    }
    base.update(kw)
    return OffTargetSite(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["score", "mit_score", "frequency"])
def test_a_unit_interval_field_accepts_both_ends_and_refuses_past_one(field: str) -> None:
    for edge in (0.0, 1.0):
        assert getattr(_site(**{field: edge}), field) == edge
    with pytest.raises(ValidationError, match="not in"):
        _site(**{field: 1.05})


def test_the_report_records_the_same_defaults_the_engine_and_api_search_with() -> None:
    engine = {k: p.default for k, p in inspect.signature(search).parameters.items()}
    api = {k: f.default for k, f in OffTargetRequest.model_fields.items()}
    report = {k: f.default for k, f in OffTargetReport.model_fields.items()}
    for engine_name, report_name in (
        ("mismatches", "mismatch_threshold"),
        ("dna_bulges", "dna_bulge_budget"),
        ("rna_bulges", "rna_bulge_budget"),
        ("cfd_threshold", "cfd_threshold"),
        ("mit_threshold", "mit_threshold"),
    ):
        assert engine[engine_name] == api[engine_name] == report[report_name], engine_name


def _report(**kw: object) -> OffTargetReport:
    base: dict[str, object] = {"spacer": "ACGTACGTACGTACGTACGT", "pam": "NGG"}
    base.update(kw)
    return OffTargetReport(**base)  # type: ignore[arg-type]


def test_a_clean_search_that_found_nothing_is_not_called_empty() -> None:
    text = _report(searched_bases=1000, resolved_bases=1000).search_description()
    assert "NO SEQUENCE WAS SEARCHED" not in text


def test_a_search_of_nothing_says_so_without_dividing_by_zero() -> None:
    text = _report(searched_bases=0, resolved_bases=0).search_description()
    assert "NO SEQUENCE WAS SEARCHED" in text


@pytest.mark.parametrize("length", GUIDE_SPACER_RANGE)
def test_a_spacer_at_either_end_of_the_guide_range_is_a_guide(length: int) -> None:
    text = _report(spacer="A" * length, searched_bases=10, resolved_bases=10)
    assert "sequence search" not in text.search_description()


def test_no_subthreshold_tail_gets_no_subthreshold_note() -> None:
    text = _report(searched_bases=10, resolved_bases=10).search_description()
    assert "sub-threshold tail" not in text


def _pop(score: float, frequency: float | None, ancestries: dict[str, float]) -> OffTargetSite:
    from alleleforge.types.offtarget import SiteOrigin

    return _site(
        score=score,
        origin=SiteOrigin.POPULATION,
        causal_allele="chr1:20:A>T",
        frequency=frequency,
        ancestries=ancestries,
    )


def test_a_population_site_without_a_frequency_is_unweighted() -> None:
    bare = _report(sites=(_pop(0.5, None, {}),))
    assert bare.is_frequency_weighted() is False
    assert bare.expected_burden() == pytest.approx(0.5)
    assert _report(sites=(_pop(0.5, 0.01, {"AFR": 0.01}),)).is_frequency_weighted() is True


def test_an_ancestry_s_worst_score_can_be_below_a_tenth() -> None:
    report = _report(sites=(_pop(0.05, 0.05, {"AFR": 0.05}),))
    assert report.ancestry_stratification() == pytest.approx({"AFR": 0.05})


def test_per_ancestry_burden_counts_each_site_where_it_belongs() -> None:
    report = _report(
        sites=(
            _pop(0.5, 0.1, {"AFR": 0.1}),
            _pop(0.4, 0.2, {"EUR": 0.2}),
            # No frequency and no ancestry: unattributed, so it counts in full for all.
            _pop(0.3, None, {}),
        )
    )
    assert report.ancestry_expected_burden() == pytest.approx(
        {"AFR": 0.5 * 0.1 + 0.3, "EUR": 0.4 * 0.2 + 0.3}
    )


@pytest.mark.parametrize(
    ("kw", "phrase", "present"),
    [
        ({"cfd_threshold": 1.05, "mit_threshold": 1.05}, "no site can clear", True),
        ({"cfd_threshold": 1.0, "mit_threshold": 1.0}, "no site can clear", False),
        ({"maf_threshold": 1.05}, "no allele can reach", True),
        ({"maf_threshold": 1.0}, "no allele can reach", False),
        ({"spacer": "A" * GUIDE_SPACER_RANGE[0]}, "not a guide length", False),
        ({"spacer": "A" * GUIDE_SPACER_RANGE[1]}, "not a guide length", False),
        ({"spacer": "A" * (GUIDE_SPACER_RANGE[1] + 1)}, "not a guide length", True),
    ],
)
def test_the_headline_notes_flag_exactly_the_unreachable(
    kw: dict[str, object], phrase: str, present: bool
) -> None:
    from alleleforge.types.offtarget import headline_notes

    notes = " ".join(headline_notes(_report(searched_bases=10, resolved_bases=10, **kw)))
    assert (phrase in notes) is present, notes


def test_a_one_base_search_still_reports_its_extent_and_coverage() -> None:
    text = _report(searched_bases=1, resolved_bases=0).search_description()
    assert "over 1 bases" in text
    assert "only 0% of the 1 requested bases" in text


def test_a_small_subthreshold_tail_is_described() -> None:
    report = _report(
        searched_bases=10, resolved_bases=10, subthreshold_score_sum=0.05, subthreshold_placements=2
    )
    assert "sub-threshold tail of 2" in report.search_description()
