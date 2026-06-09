"""Tests for the Phase 11 report builder."""

from __future__ import annotations

from alleleforge.report.builder import (
    RESEARCH_USE_DISCLAIMER,
    DesignReport,
    build_report,
)
from alleleforge.types.candidate import RankedMenu


def test_build_report_basic(prime_menu: RankedMenu) -> None:
    report = build_report(prime_menu, variant="chr2:70:A>C", intent="install")
    assert isinstance(report, DesignReport)
    assert report.disclaimer == RESEARCH_USE_DISCLAIMER
    assert report.variant == "chr2:70:A>C"
    assert report.intent == "install"
    assert len(report.candidates) == len(prime_menu.candidates)


def test_report_carries_provenance(prime_menu: RankedMenu) -> None:
    report = build_report(prime_menu)
    assert report.provenance is not None
    assert report.provenance.alleleforge_version


def test_intent_falls_back_to_provenance(prime_menu: RankedMenu) -> None:
    # design() stamps intent into provenance; build_report reads it if not given.
    report = build_report(prime_menu)
    assert report.intent == "install"


def test_ranks_are_one_based_and_ordered(prime_menu: RankedMenu) -> None:
    report = build_report(prime_menu)
    assert [c.rank for c in report.candidates] == list(range(1, len(report.candidates) + 1))


def test_pareto_flag_matches_menu(prime_menu: RankedMenu) -> None:
    report = build_report(prime_menu)
    flagged = {c.rank - 1 for c in report.candidates if c.on_pareto_front}
    assert flagged == set(prime_menu.pareto_front)


def test_every_candidate_axes_populated(prime_menu: RankedMenu) -> None:
    report = build_report(prime_menu)
    for c in report.candidates:
        assert c.efficiency is not None
        assert c.outcome_top  # at least one outcome allele
        assert c.n_offtarget_sites is not None
        assert c.reagent and c.reagent != "no reagent"


def test_candidate_carries_aggregate_specificity(prime_menu: RankedMenu) -> None:
    report = build_report(prime_menu)
    for c in report.candidates:
        assert c.offtarget_specificity is not None
        assert 0.0 < c.offtarget_specificity <= 1.0


def test_offtarget_table_is_ancestry_stratified(abe_menu: RankedMenu) -> None:
    report = build_report(abe_menu)
    top = report.candidates[0]
    # ancestry rows are sorted worst-first when present
    scores = [r.worst_score for r in top.offtarget_by_ancestry]
    assert scores == sorted(scores, reverse=True)


def test_oligos_attached_by_default(nuclease_menu: RankedMenu) -> None:
    report = build_report(nuclease_menu)
    assert report.candidates[0].oligos is not None


def test_oligos_can_be_omitted(nuclease_menu: RankedMenu) -> None:
    report = build_report(nuclease_menu, with_oligos=False)
    assert all(c.oligos is None for c in report.candidates)


def test_top_alleles_caps_outcomes(prime_menu: RankedMenu) -> None:
    report = build_report(prime_menu, top_alleles=2)
    assert all(len(c.outcome_top) <= 2 for c in report.candidates)


def test_report_json_roundtrips(prime_menu: RankedMenu) -> None:
    report = build_report(prime_menu)
    restored = DesignReport.model_validate_json(report.model_dump_json())
    assert restored == report


def test_ancestry_stratification_populated(ancestry_menu: RankedMenu) -> None:
    report = build_report(ancestry_menu)
    top = report.candidates[0]
    by = {r.ancestry: r.worst_score for r in top.offtarget_by_ancestry}
    # the reference site (score 0.18) contributes to every ancestry; the
    # population site (0.74) only to afr — so afr is the worst-affected.
    assert by["afr"] == 0.74
    assert by["eur"] == 0.18
    assert [r.worst_score for r in top.offtarget_by_ancestry] == sorted(
        (r.worst_score for r in top.offtarget_by_ancestry), reverse=True
    )
