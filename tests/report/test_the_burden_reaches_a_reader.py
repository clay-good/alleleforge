"""The one number that separates a rare off-target from a universal one reached nobody.

`OffTargetReport.expected_burden()` weights each site by the probability a genome
actually carries it. `worst_score()` and `specificity_score()` are frequency-blind, so a
0.1%-MAF population hit and a universal reference hit of the same raw score are
identical in both — the burden weights them a thousandfold apart. Population-aware
off-target nomination is the thing this project exists to do, and the shipped spec says
the burden is exposed "alongside the frequency-blind `worst_score` and
`specificity_score` ... in the summary numbers".

It was on the model and on no surface. Not the HTML, not the PDF, not the TSV export,
not `aforge offtarget`, not `POST /api/offtarget`. Only tests called it — the same shape
as R247's `apply_to` and R248's `reason`, three rounds running.

It is reported only when some site's presence is probabilistic: with reference sites
alone the burden is the unweighted score sum and adds a number without adding a fact.
Every surface asks `is_frequency_weighted()` so they agree on when it is worth showing.
"""

from __future__ import annotations

from alleleforge.types.offtarget import (
    OffTargetReport,
    OffTargetSite,
    ScoreMethod,
    SiteOrigin,
)
from alleleforge.types.sequence import GenomicInterval, Strand


def _locus(start: int = 100) -> GenomicInterval:
    return GenomicInterval(chrom="chr2", start=start, end=start + 20, strand=Strand.PLUS)


def _ref_site(score: float) -> OffTargetSite:
    return OffTargetSite(locus=_locus(), mismatches=2, score=score, score_method=ScoreMethod.CFD)


def _pop_site(score: float, freq: float) -> OffTargetSite:
    return OffTargetSite(
        locus=_locus(400),
        mismatches=1,
        score=score,
        score_method=ScoreMethod.CFD,
        origin=SiteOrigin.POPULATION,
        causal_allele="chr2:405:A>G",
        populations=("afr",),
        frequency=freq,
        ancestries={"afr": freq},
    )


def _report(*sites: OffTargetSite) -> OffTargetReport:
    return OffTargetReport(spacer="A" * 20, pam="NGG", sites=sites)


def test_the_predicate_fires_only_for_a_probabilistic_site() -> None:
    assert not _report(_ref_site(0.9)).is_frequency_weighted()
    assert not _report().is_frequency_weighted()
    assert _report(_ref_site(0.9), _pop_site(0.9, 0.001)).is_frequency_weighted()


def test_the_renders_show_it(ancestry_menu: object) -> None:
    """The shared ancestry fixture carries a population site, so all three must state it."""
    from alleleforge.report.builder import build_report
    from alleleforge.report.export import report_to_json, report_to_tsv
    from alleleforge.report.html import render_html
    from alleleforge.report.pdf import render_pdf
    from alleleforge.types.candidate import RankedMenu

    assert isinstance(ancestry_menu, RankedMenu)
    report = build_report(ancestry_menu)
    top = report.candidates[0]
    assert top.offtarget_expected_burden is not None, "the fixture is not frequency-weighted"

    assert "expected burden" in render_html(report)
    assert "expected burden" in render_pdf(report).decode("latin-1", errors="ignore")
    assert "offtarget_expected_burden" in report_to_tsv(report)
    assert "offtarget_expected_burden" in report_to_json(report)


def test_the_web_summary_carries_it() -> None:
    from alleleforge.web.api.models import OffTargetResponse

    weighted = OffTargetResponse.from_report(_report(_ref_site(0.9), _pop_site(0.9, 0.001)))
    assert weighted.expected_burden is not None
    assert weighted.expected_burden < weighted.report.n_sites  # down-weighted, not summed
    # ...and stays absent when it would only restate the score sum.
    plain = OffTargetResponse.from_report(_report(_ref_site(0.9)))
    assert plain.expected_burden is None


def test_every_render_shows_it_when_it_says_something() -> None:
    from alleleforge.report.builder import CandidateReport

    assert "offtarget_expected_burden" in CandidateReport.model_fields
