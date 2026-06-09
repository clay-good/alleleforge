"""Tests for off-target site/report models and ancestry stratification."""

from __future__ import annotations

import pytest

from alleleforge.types.offtarget import (
    OffTargetReport,
    OffTargetSite,
    ScoreMethod,
    SiteOrigin,
)
from alleleforge.types.sequence import GenomicInterval, Strand


def _locus(start: int = 0, end: int = 20) -> GenomicInterval:
    return GenomicInterval(chrom="chr2", start=start, end=end, strand=Strand.PLUS)


def _ref_site(score: float) -> OffTargetSite:
    return OffTargetSite(locus=_locus(), mismatches=2, score=score, score_method=ScoreMethod.CFD)


def _pop_site(score: float, ancestry: str, freq: float) -> OffTargetSite:
    return OffTargetSite(
        locus=_locus(50, 70),
        mismatches=1,
        score=score,
        score_method=ScoreMethod.CFD,
        origin=SiteOrigin.POPULATION,
        causal_allele="chr2:55:A>G",
        populations=(ancestry,),
        frequency=freq,
        ancestries={ancestry: freq},
    )


def test_site_score_range_enforced() -> None:
    with pytest.raises(ValueError, match="score"):
        OffTargetSite(locus=_locus(), mismatches=0, score=1.5, score_method=ScoreMethod.CFD)


def test_site_negative_counts_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        OffTargetSite(locus=_locus(), mismatches=-1, score=0.5, score_method=ScoreMethod.MIT)


def test_population_site_requires_causal_allele() -> None:
    with pytest.raises(ValueError, match="causal_allele"):
        OffTargetSite(
            locus=_locus(),
            mismatches=1,
            score=0.5,
            score_method=ScoreMethod.CFD,
            origin=SiteOrigin.POPULATION,
        )


def test_frequency_range_enforced() -> None:
    with pytest.raises(ValueError, match="frequency"):
        OffTargetSite(
            locus=_locus(),
            mismatches=1,
            score=0.5,
            score_method=ScoreMethod.CFD,
            origin=SiteOrigin.PATIENT,
            causal_allele="chr2:55:A>G",
            frequency=2.0,
        )


def test_report_counts_and_population_filter() -> None:
    rep = OffTargetReport(
        spacer="A" * 20,
        pam="NGG",
        sites=(_ref_site(0.3), _pop_site(0.9, "AFR", 0.02)),
    )
    assert rep.n_sites == 2
    assert len(rep.population_sites) == 1
    assert rep.worst_score() == pytest.approx(0.9)


def test_worst_score_empty_report() -> None:
    assert OffTargetReport(spacer="A" * 20, pam="NGG").worst_score() == 0.0


def test_specificity_score_is_one_without_off_targets() -> None:
    assert OffTargetReport(spacer="A" * 20, pam="NGG").specificity_score() == 1.0


def test_specificity_score_matches_hsu_formula() -> None:
    rep = OffTargetReport(
        spacer="A" * 20, pam="NGG", sites=(_ref_site(0.5), _pop_site(0.3, "AFR", 0.02))
    )
    # 1 / (1 + 0.5 + 0.3)
    assert rep.specificity_score() == pytest.approx(1.0 / 1.8)


def test_specificity_score_distinguishes_total_burden() -> None:
    # Same worst-case off-target, but one guide has more of them -> less specific.
    one = OffTargetReport(spacer="A" * 20, pam="NGG", sites=(_ref_site(0.6),))
    many = OffTargetReport(
        spacer="A" * 20, pam="NGG", sites=(_ref_site(0.6), _ref_site(0.4), _ref_site(0.4))
    )
    assert one.worst_score() == many.worst_score()  # worst-case can't tell them apart
    assert one.specificity_score() > many.specificity_score()  # aggregate can


def test_ancestry_stratification_reference_contributes_to_all() -> None:
    rep = OffTargetReport(
        spacer="A" * 20,
        pam="NGG",
        sites=(
            _ref_site(0.4),
            _pop_site(0.9, "AFR", 0.02),
            _pop_site(0.2, "EUR", 0.01),
        ),
    )
    strata = rep.ancestry_stratification()
    # AFR: max(ref 0.4, pop 0.9) = 0.9 ; EUR: max(ref 0.4, pop 0.2) = 0.4
    assert strata["AFR"] == pytest.approx(0.9)
    assert strata["EUR"] == pytest.approx(0.4)
    assert rep.worst_ancestry() == ("AFR", pytest.approx(0.9))


def test_ancestry_stratification_is_deterministically_ordered() -> None:
    # The strata mapping must come out in sorted-key order, and a worst-case tie
    # must resolve to the alphabetically-first ancestry, so the serialized report
    # is byte-stable regardless of the process hash seed (a bare set iteration
    # would otherwise vary the key order — and the tie-break — run to run).
    rep = OffTargetReport(
        spacer="A" * 20,
        pam="NGG",
        sites=(
            _pop_site(0.5, "eur", 0.10),
            _pop_site(0.5, "afr", 0.10),  # ties with eur at the worst score
            _pop_site(0.3, "eas", 0.05),
        ),
    )
    strata = rep.ancestry_stratification()
    assert list(strata) == sorted(strata)  # deterministic key order
    assert rep.worst_ancestry() == ("afr", pytest.approx(0.5))  # tie -> alphabetically first


def test_worst_ancestry_none_without_annotation() -> None:
    rep = OffTargetReport(spacer="A" * 20, pam="NGG", sites=(_ref_site(0.5),))
    assert rep.worst_ancestry() is None


def test_reference_bias_motivating_case() -> None:
    """A minor allele creating a high-CFD de-novo off-target in one ancestry.

    Mirrors the BCL11A / rs114518452 reference-bias case (Cancellieri &
    Pinello, Nat Genet 2023): reference-only scanning would miss the
    population-specific high-CFD site entirely.
    """
    reference_only = OffTargetReport(spacer="C" * 20, pam="NGG", sites=(_ref_site(0.15),))
    population_aware = OffTargetReport(
        spacer="C" * 20,
        pam="NGG",
        sites=(_ref_site(0.15), _pop_site(0.95, "AFR", 0.05)),
    )
    assert reference_only.worst_ancestry() is None
    assert population_aware.worst_ancestry() == ("AFR", pytest.approx(0.95))
    assert population_aware.worst_score() > reference_only.worst_score()
