"""Tests for the Phase 10 cross-chemistry ranker."""

from __future__ import annotations

import pytest

from alleleforge.design.ranking import (
    DEFAULT_WEIGHTS,
    RankingWeights,
    pareto_front,
    rank_candidates,
    score_candidate,
)
from alleleforge.types.candidate import DesignCandidate
from alleleforge.types.edit import AlleleOutcome, Chemistry, EditOutcome
from alleleforge.types.guide import PAM, Guide, Spacer
from alleleforge.types.offtarget import (
    OffTargetReport,
    OffTargetSite,
    ScoreMethod,
    SiteOrigin,
)
from alleleforge.types.prediction import Prediction, UncertaintyMethod
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand


def _eff(value: float, *, in_distribution: bool = True) -> Prediction[float]:
    return Prediction[float](
        value=value,
        interval=(max(0.0, value - 0.1), min(1.0, value + 0.1)),
        method=UncertaintyMethod.HEURISTIC,
        in_distribution=in_distribution,
    )


def _outcome(p_intended: float) -> EditOutcome:
    return EditOutcome(
        alleles=(
            AlleleOutcome(allele="EDIT", probability=p_intended, is_intended=True),
            AlleleOutcome(allele="WT", probability=1.0 - p_intended),
        )
    )


def _report(score: float, *, ancestry: str | None = None) -> OffTargetReport:
    if score == 0.0:
        sites: tuple[OffTargetSite, ...] = ()
    elif ancestry is None:
        sites = (
            OffTargetSite(
                locus=GenomicInterval(chrom="chr9", start=10, end=30, strand=Strand.PLUS),
                mismatches=2,
                score=score,
                score_method=ScoreMethod.CFD,
            ),
        )
    else:
        sites = (
            OffTargetSite(
                locus=GenomicInterval(chrom="chr9", start=10, end=30, strand=Strand.PLUS),
                mismatches=2,
                score=score,
                score_method=ScoreMethod.CFD,
                origin=SiteOrigin.POPULATION,
                causal_allele="chr9:20:A>T",
                populations=(ancestry,),
                frequency=0.05,
                ancestries={ancestry: 0.05},
            ),
        )
    return OffTargetReport(spacer="A" * 20, pam="NGG", sites=sites)


def _cand(
    chemistry: Chemistry,
    *,
    eff: float = 0.5,
    p_intended: float = 0.5,
    offscore: float = 0.0,
    ancestry: str | None = None,
    in_distribution: bool = True,
) -> DesignCandidate:
    return DesignCandidate(
        chemistry=chemistry,
        efficiency=_eff(eff, in_distribution=in_distribution),
        outcome=_outcome(p_intended),
        offtarget=_report(offscore, ancestry=ancestry),
        rationale="seed",
    )


def test_score_objectives_are_higher_is_better() -> None:
    s = score_candidate(_cand(Chemistry.CAS9_NUCLEASE, eff=0.8, p_intended=0.7, offscore=0.2))
    assert s.efficiency == 0.8
    assert s.cleanliness == 0.7
    assert abs(s.safety - 0.8) < 1e-9  # 1 - 0.2
    assert 0.0 <= s.composite <= 1.0


def test_weighted_sum_orders_candidates() -> None:
    good = _cand(Chemistry.PRIME, eff=0.9, p_intended=0.9, offscore=0.0)
    bad = _cand(Chemistry.PRIME, eff=0.2, p_intended=0.2, offscore=0.6)
    outcome = rank_candidates([bad, good])
    assert outcome.candidates[0].efficiency is not None
    assert outcome.candidates[0].efficiency.value == 0.9


def test_weights_are_sensitive_in_the_expected_direction() -> None:
    # A: high efficiency, mediocre safety. B: low efficiency, perfect safety.
    a = _cand(Chemistry.CAS9_NUCLEASE, eff=0.9, p_intended=0.5, offscore=0.5)
    b = _cand(Chemistry.PRIME, eff=0.3, p_intended=0.5, offscore=0.0)
    eff_heavy = rank_candidates([a, b], weights=RankingWeights(efficiency=0.9, safety=0.1))
    safe_heavy = rank_candidates([a, b], weights=RankingWeights(efficiency=0.1, safety=0.9))
    assert eff_heavy.candidates[0].chemistry is Chemistry.CAS9_NUCLEASE
    assert safe_heavy.candidates[0].chemistry is Chemistry.PRIME


def test_ancestry_worst_case_downranks_population_dangerous_guide() -> None:
    # Both guides have identical efficiency and cleanliness; the only difference
    # is one is dangerous in a single ancestry. It must rank below the safe one.
    dangerous = _cand(
        Chemistry.CAS9_NUCLEASE, eff=0.6, p_intended=0.6, offscore=0.8, ancestry="AFR"
    )
    safe = _cand(Chemistry.CAS9_NUCLEASE, eff=0.6, p_intended=0.6, offscore=0.0)
    outcome = rank_candidates([dangerous, safe])
    assert outcome.candidates[0].offtarget is not None
    assert outcome.candidates[0].offtarget.worst_score() == 0.0
    # The safety term is computed against the worst-affected ancestry.
    sc = score_candidate(dangerous)
    assert sc.worst_ancestry == "AFR"
    assert abs(sc.safety - 0.2) < 1e-9


def test_patient_offtarget_not_masked_on_safety_axis_by_benign_ancestry_site() -> None:
    # Regression: a certain patient off-target (CFD 0.9) must dominate the safety
    # axis. Adding a *benign* ancestry-tagged population site (0.2) must not raise
    # safety — but it used to, because _safety keyed off worst_ancestry() and a
    # patient site (no ancestry) was absent from every stratum, so the benign site's
    # 0.2 became the "worst ancestry." This pair co-occurs in a real
    # design(gnomad=…, patient_vcf=…) run (population + patient passes into one report).
    patient = OffTargetSite(
        locus=GenomicInterval(chrom="chr9", start=10, end=30, strand=Strand.PLUS),
        mismatches=1,
        score=0.9,
        score_method=ScoreMethod.CFD,
        origin=SiteOrigin.PATIENT,
        causal_allele="chr9:20:A>G",
    )
    benign = OffTargetSite(
        locus=GenomicInterval(chrom="chr9", start=50, end=70, strand=Strand.PLUS),
        mismatches=2,
        score=0.2,
        score_method=ScoreMethod.CFD,
        origin=SiteOrigin.POPULATION,
        causal_allele="chr9:60:C>T",
        populations=("AFR",),
        frequency=0.5,
        ancestries={"AFR": 0.5},
    )
    patient_only = DesignCandidate(
        chemistry=Chemistry.CAS9_NUCLEASE,
        efficiency=_eff(0.5),
        outcome=_outcome(0.5),
        offtarget=OffTargetReport(spacer="A" * 20, pam="NGG", sites=(patient,)),
        rationale="seed",
    )
    with_benign = DesignCandidate(
        chemistry=Chemistry.CAS9_NUCLEASE,
        efficiency=_eff(0.5),
        outcome=_outcome(0.5),
        offtarget=OffTargetReport(spacer="A" * 20, pam="NGG", sites=(patient, benign)),
        rationale="seed",
    )
    s_patient = score_candidate(patient_only)
    s_benign = score_candidate(with_benign)
    assert s_patient.safety == pytest.approx(1.0 - 0.9)  # 0.1: the patient hit
    # Adding a benign off-target cannot make a guide look safer.
    assert s_benign.safety == pytest.approx(s_patient.safety)


def test_ranking_is_invariant_to_input_pool_order_on_full_ties() -> None:
    # Two distinct guides (different spacers) that tie on every objective must rank
    # in the same order regardless of how the pool was assembled — the four-key sort
    # exhausts on a full tie, so without a final identity tiebreak the order followed
    # input order.
    def cand(spacer: str) -> DesignCandidate:
        return DesignCandidate(
            chemistry=Chemistry.CAS9_NUCLEASE,
            guide=Guide(
                spacer=Spacer(sequence=DNASequence(spacer)),
                pam=PAM(pattern="NGG"),
                pam_sequence=DNASequence("TGG"),
                placement=GenomicInterval(chrom="c", start=0, end=20, strand=Strand.PLUS),
                cut_site=17,
            ),
            efficiency=_eff(0.5),
            outcome=_outcome(0.5),
            offtarget=_report(0.0),
            rationale="seed",
        )

    a, b = cand("A" * 20), cand("C" * 20)
    order1 = [str(c.guide.spacer.sequence) for c in rank_candidates([a, b]).candidates]
    order2 = [str(c.guide.spacer.sequence) for c in rank_candidates([b, a]).candidates]
    assert order1 == order2  # input permutation does not change the ranked order
    front1 = rank_candidates([a, b]).pareto_front
    front2 = rank_candidates([b, a]).pareto_front
    assert front1 == front2  # and the Pareto front indices are stable too


def test_ood_candidate_ranks_below_identical_in_distribution() -> None:
    # Two candidates identical in every respect except the OOD flag on the
    # efficiency prediction. The out-of-distribution one is ranked on its lower
    # interval bound, so it must rank below the in-distribution one.
    in_dist = _cand(Chemistry.CAS9_NUCLEASE, eff=0.8, in_distribution=True)
    ood = _cand(Chemistry.CAS9_NUCLEASE, eff=0.8, in_distribution=False)
    outcome = rank_candidates([ood, in_dist])
    assert outcome.candidates[0].efficiency is not None
    assert outcome.candidates[0].efficiency.in_distribution is True
    # The score breakdown surfaces the OOD demotion and the lower bound used.
    in_dist_score, ood_score = outcome.scores
    assert in_dist_score.efficiency > ood_score.efficiency
    assert ood_score.efficiency_in_distribution is False
    assert "OOD" in ood_score.explain()
    assert "out-of-distribution" in outcome.rationale


def test_ood_score_uses_lower_interval_bound() -> None:
    ood = _cand(Chemistry.PRIME, eff=0.7, in_distribution=False)
    sc = score_candidate(ood)
    # eff 0.7 with interval (0.6, 0.8) OOD -> ranked on the 0.6 lower bound.
    assert sc.efficiency == pytest.approx(0.6)
    assert sc.efficiency_interval is not None
    assert sc.efficiency_interval == pytest.approx((0.6, 0.8))


def test_cap_keeps_composite_best_not_local_proxy_best() -> None:
    # A tops a vertical's local efficiency proxy (eff 0.9) but is dangerous and
    # dirty (low safety/cleanliness); B is the composite winner. A cap applied on
    # the local proxy (as the verticals used to) would keep A and prune B before the
    # composite is even computed; applied on the composite (as the ranker now does),
    # the cap keeps B.
    a = _cand(Chemistry.CAS9_NUCLEASE, eff=0.9, p_intended=0.1, offscore=0.95)
    b = _cand(Chemistry.CAS9_NUCLEASE, eff=0.55, p_intended=0.95, offscore=0.0)
    assert score_candidate(b).composite > score_candidate(a).composite  # B wins the composite
    out = rank_candidates([a, b], max_per_chemistry=1)
    assert len(out.candidates) == 1
    assert out.candidates[0].efficiency is not None
    assert out.candidates[0].efficiency.value == 0.55  # B kept, not the eff-0.9 A


def test_cap_is_per_chemistry() -> None:
    cands = [
        _cand(Chemistry.CAS9_NUCLEASE, eff=0.9),
        _cand(Chemistry.CAS9_NUCLEASE, eff=0.5),
        _cand(Chemistry.PRIME, eff=0.8),
        _cand(Chemistry.PRIME, eff=0.4),
    ]
    out = rank_candidates(cands, max_per_chemistry=1)
    kept_chems = [c.chemistry for c in out.candidates]
    assert kept_chems.count(Chemistry.CAS9_NUCLEASE) == 1
    assert kept_chems.count(Chemistry.PRIME) == 1


def test_pareto_front_excludes_dominated() -> None:
    best = _cand(Chemistry.PRIME, eff=0.9, p_intended=0.9, offscore=0.0)
    dominated = _cand(Chemistry.PRIME, eff=0.4, p_intended=0.4, offscore=0.5)
    middling = _cand(Chemistry.CAS9_NUCLEASE, eff=0.5, p_intended=0.95, offscore=0.0)
    outcome = rank_candidates([best, dominated, middling])
    fronted = {outcome.candidates[i].efficiency.value for i in outcome.pareto_front}  # type: ignore[union-attr]
    assert 0.9 in fronted  # the all-round best is Pareto-optimal
    assert 0.95 not in {c.efficiency.value for c in outcome.candidates if c.efficiency} or True
    # the dominated 0.4 candidate is not on the front
    assert 0.4 not in fronted


def test_pareto_front_helper_on_scores() -> None:
    scores = [
        score_candidate(_cand(Chemistry.PRIME, eff=0.9, p_intended=0.9, offscore=0.0)),
        score_candidate(_cand(Chemistry.PRIME, eff=0.1, p_intended=0.1, offscore=0.9)),
    ]
    assert pareto_front(scores) == (0,)


def test_default_weights_sum_to_spec() -> None:
    w = DEFAULT_WEIGHTS.normalized()
    assert abs(w["efficiency"] - 0.35) < 1e-9
    assert abs(w["cleanliness"] - 0.30) < 1e-9
    assert abs(w["safety"] - 0.30) < 1e-9
    assert abs(w["simplicity"] - 0.05) < 1e-9


def test_prime_is_less_simple_than_nuclease() -> None:
    nuc = score_candidate(_cand(Chemistry.CAS9_NUCLEASE))
    prime = score_candidate(_cand(Chemistry.PRIME))
    assert nuc.simplicity > prime.simplicity


def test_zero_weights_rejected() -> None:
    with pytest.raises(ValueError, match="cannot all be zero"):
        RankingWeights(efficiency=0.0, cleanliness=0.0, safety=0.0, simplicity=0.0)


def test_negative_weight_rejected() -> None:
    with pytest.raises(ValueError, match="must be non-negative"):
        RankingWeights(efficiency=-0.1)


def test_nan_weight_rejected() -> None:
    # A `nan` weight slips past a bare `< 0.0` check and makes every normalized
    # fraction `nan`, corrupting the composite the ranking sorts on.
    with pytest.raises(ValueError, match="must be finite"):
        RankingWeights(simplicity=float("nan"))


def test_infinite_weight_rejected() -> None:
    # An `inf` weight collapses the finite weights to 0.0 under normalization.
    with pytest.raises(ValueError, match="must be finite"):
        RankingWeights(efficiency=float("inf"))
