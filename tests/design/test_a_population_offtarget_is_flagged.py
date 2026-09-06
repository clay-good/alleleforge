"""The flag for the project's headline risk was emitted by an untested line.

`offtarget_flags` returns `population-offtarget` when a candidate's off-target report
contains sites that exist only on population alleles — the nomination this tool exists to
make. Coverage showed that line never ran: the suite exercised the unsearched case and the
clean case, and never a report with a population site.

Nothing was broken. But an emission site nothing runs is one nobody would notice losing,
and this is the flag that tells a reader their guide's off-targets are not in everyone's
genome.
"""

from __future__ import annotations

from alleleforge.design.offtarget_flags import offtarget_flags
from alleleforge.report.builder import CAVEAT_FLAGS
from alleleforge.types.offtarget import (
    OffTargetReport,
    OffTargetSite,
    ScoreMethod,
    SiteOrigin,
)
from alleleforge.types.sequence import GenomicInterval, Strand


def _site(origin: SiteOrigin, score: float = 0.4) -> OffTargetSite:
    return OffTargetSite(
        locus=GenomicInterval(chrom="chr2", start=100, end=120, strand=Strand.PLUS),
        mismatches=1,
        score=score,
        score_method=ScoreMethod.CFD,
        origin=origin,
        causal_allele="chr2:105:A>G" if origin is not SiteOrigin.REFERENCE else None,
        populations=("afr",) if origin is SiteOrigin.POPULATION else (),
        frequency=0.1 if origin is SiteOrigin.POPULATION else None,
        ancestries={"afr": 0.1} if origin is SiteOrigin.POPULATION else {},
    )


def _report(*sites: OffTargetSite) -> OffTargetReport:
    return OffTargetReport(spacer="A" * 20, pam="NGG", sites=sites)


def test_a_population_site_raises_the_flag() -> None:
    assert "population-offtarget" in offtarget_flags(_report(_site(SiteOrigin.POPULATION)))


def test_a_reference_only_report_does_not() -> None:
    assert offtarget_flags(_report(_site(SiteOrigin.REFERENCE))) == []


def test_an_unsearched_candidate_says_so_instead() -> None:
    assert offtarget_flags(None) == ["offtarget-not-searched"]


def test_a_high_scoring_population_site_raises_both() -> None:
    """The two flags are independent: a dangerous site that is also population-specific."""
    flags = offtarget_flags(_report(_site(SiteOrigin.POPULATION, score=0.95)))
    assert "population-offtarget" in flags
    assert any(flag.startswith("offtarget-high") for flag in flags)


def test_the_flag_is_classified() -> None:
    """Per the classification contract: emitted means explained."""
    assert "population-offtarget" in CAVEAT_FLAGS
