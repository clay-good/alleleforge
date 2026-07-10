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


def _report(sites: tuple[OffTargetSite, ...], nominal: str | None) -> OffTargetReport:
    return OffTargetReport(
        spacer="A" * 20,
        pam="NGG",
        sites=sites,
        mismatch_threshold=4,
        reference_build="hg38",
        scorer="CFD",
        score_matrix=nominal,
    )


def test_effective_matrix_reconciles_per_site_fallbacks() -> None:
    # The report-level matrix records the *nominal* configured matrix; the effective
    # one must reflect what the reported sites were actually scored by, so an
    # all-fallback table is not labeled published CFD.
    pub = "doench-2016-cfd"
    approx = "doench-2016-seed-tolerance-approximation"

    def site(matrix: str) -> OffTargetSite:
        return OffTargetSite(
            locus=_locus(),
            mismatches=1,
            score=0.5,
            score_method=ScoreMethod.CFD,
            score_matrix=matrix,
        )

    # No sites -> fall back to the nominal configured matrix.
    assert _report((), pub).effective_matrix() == pub
    # All reported sites fell back -> the effective matrix is the approximation.
    assert _report((site(approx),), pub).effective_matrix() == approx
    # All published -> published.
    assert _report((site(pub),), pub).effective_matrix() == pub
    # Mixed -> both, joined and sorted, never silently claiming published alone.
    assert _report((site(pub), site(approx)), pub).effective_matrix() == f"{pub} + {approx}"


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


def test_specificity_score_includes_subthreshold_tail() -> None:
    # Two guides with identical *reported* sites but different sub-threshold tails
    # must get different specificity — the promiscuous one (large near-threshold
    # tail) is less specific, matching the CRISPOR/Hsu sum over all candidate sites.
    clean = OffTargetReport(spacer="A" * 20, pam="NGG", sites=(_ref_site(0.6),))
    promiscuous = OffTargetReport(
        spacer="A" * 20, pam="NGG", sites=(_ref_site(0.6),), subthreshold_score_sum=0.5
    )
    assert clean.worst_score() == promiscuous.worst_score()  # top hits are identical
    assert clean.specificity_score() > promiscuous.specificity_score()
    assert promiscuous.specificity_score() == pytest.approx(1.0 / (1.0 + 0.6 + 0.5))


def test_expected_burden_weights_by_carrying_frequency() -> None:
    # A MAF-floor population off-target and a universal reference one with the same
    # raw score contribute very different expected burdens; the frequency-blind
    # worst-case still reports the higher raw score.
    rep = OffTargetReport(
        spacer="A" * 20,
        pam="NGG",
        sites=(_pop_site(0.9, "AFR", 0.001), _ref_site(0.9)),
    )
    assert rep.worst_score() == pytest.approx(0.9)  # frequency-blind: same raw score
    assert rep.expected_burden() == pytest.approx(0.9 * 0.001 + 0.9)  # rare down-weighted


def test_expected_burden_separates_rare_from_universal() -> None:
    rare = OffTargetReport(spacer="A" * 20, pam="NGG", sites=(_pop_site(0.9, "AFR", 0.001),))
    common = OffTargetReport(spacer="A" * 20, pam="NGG", sites=(_pop_site(0.9, "AFR", 0.5),))
    assert rare.worst_score() == common.worst_score()  # worst-case can't tell them apart
    assert rare.expected_burden() < common.expected_burden()  # the burden can


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


def _patient_site(score: float) -> OffTargetSite:
    # A patient site is certain in this individual's genome: no ancestry frequency.
    return OffTargetSite(
        locus=_locus(80, 100),
        mismatches=1,
        score=score,
        score_method=ScoreMethod.CFD,
        origin=SiteOrigin.PATIENT,
        causal_allele="chr2:88:A>G",
    )


def test_patient_site_floors_every_ancestry_stratum() -> None:
    # A patient off-target is certain in the evaluated genome (like a reference
    # site), so it must contribute to every ancestry's worst case. Otherwise a
    # dangerous patient hit (absent from every stratum) is invisible to
    # worst_ancestry — and a benign ancestry-tagged site masks it on the safety
    # axis. This is the pair that co-occurs in a real design(gnomad=…, patient_vcf=…)
    # run (population pass + patient pass into one report).
    rep = OffTargetReport(
        spacer="A" * 20,
        pam="NGG",
        sites=(_patient_site(0.9), _pop_site(0.2, "AFR", 0.5)),
    )
    strata = rep.ancestry_stratification()
    assert strata["AFR"] == pytest.approx(0.9)  # the 0.9 patient hit floors AFR
    assert rep.worst_ancestry() == ("AFR", pytest.approx(0.9))
    # worst_ancestry now equals the global worst, so the safety axis cannot be
    # gamed lower by adding a benign ancestry-tagged site.
    assert rep.worst_ancestry()[1] == pytest.approx(rep.worst_score())


def test_population_site_without_ancestry_breakdown_floors_every_stratum() -> None:
    # A population site with a KNOWN frequency but an EMPTY per-ancestry breakdown
    # (a report built from a source giving only a global AF) is neither reference
    # nor patient, yet its ancestry attribution is unknown. It must still contribute
    # to every stratum's worst case — exactly as expected_burden already counts it —
    # or it vanishes from the stratified view while a benign ancestry-tagged site
    # makes worst_ancestry non-None, understating the genome-wide worst on the
    # ranking safety axis (the R24 sibling of the R11 patient-masking fix).
    dangerous = OffTargetSite(
        locus=_locus(100, 120),
        mismatches=1,
        score=0.9,
        score_method=ScoreMethod.CFD,
        origin=SiteOrigin.POPULATION,
        causal_allele="chr2:110:A>G",
        frequency=0.9,
        ancestries={},  # global AF known, per-ancestry breakdown absent
    )
    rep = OffTargetReport(
        spacer="A" * 20,
        pam="NGG",
        sites=(dangerous, _pop_site(0.2, "AFR", 0.5)),
    )
    strata = rep.ancestry_stratification()
    assert strata["AFR"] == pytest.approx(0.9)  # the unattributed 0.9 hit floors AFR
    assert rep.worst_ancestry() == ("AFR", pytest.approx(0.9))
    # The stratified worst equals the global worst and matches expected_burden's
    # accounting: adding a benign ancestry-tagged site cannot lower the safety axis.
    assert rep.worst_ancestry()[1] == pytest.approx(rep.worst_score())
    assert rep.expected_burden() == pytest.approx(0.9 * 0.9 + 0.2 * 0.5)


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
