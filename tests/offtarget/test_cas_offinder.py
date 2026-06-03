"""Tests for the optional Cas-OFFinder cross-check adapter."""

from __future__ import annotations

from alleleforge.offtarget.cas_offinder_adapter import CasOffinderAdapter
from alleleforge.types.offtarget import OffTargetReport, OffTargetSite, ScoreMethod, SiteOrigin
from alleleforge.types.sequence import GenomicInterval, Strand


def _site(start: int, origin: SiteOrigin) -> OffTargetSite:
    return OffTargetSite(
        locus=GenomicInterval(chrom="chr2", start=start, end=start + 20, strand=Strand.PLUS),
        mismatches=1,
        score=0.5,
        score_method=ScoreMethod.CFD,
        origin=origin,
        causal_allele="chr2:1:A>G" if origin is not SiteOrigin.REFERENCE else None,
    )


def _report(*sites: OffTargetSite) -> OffTargetReport:
    return OffTargetReport(spacer="A" * 20, pam="NGG", sites=sites)


def test_available_reflects_path() -> None:
    assert CasOffinderAdapter(binary="definitely-not-a-real-binary-xyz").available() is False


def test_reference_loci_excludes_population_sites() -> None:
    report = _report(_site(10, SiteOrigin.REFERENCE), _site(50, SiteOrigin.POPULATION))
    loci = CasOffinderAdapter.reference_loci(report)
    assert loci == {("chr2", 10, Strand.PLUS)}  # population site has no Cas-OFFinder counterpart


def test_agreement_has_no_disagreements() -> None:
    report = _report(_site(10, SiteOrigin.REFERENCE))
    diff = CasOffinderAdapter().disagreements(report, {("chr2", 10, Strand.PLUS)})
    assert diff["only_alleleforge"] == set()
    assert diff["only_cas_offinder"] == set()


def test_disagreements_flagged_both_ways() -> None:
    report = _report(_site(10, SiteOrigin.REFERENCE))
    diff = CasOffinderAdapter().disagreements(report, {("chr2", 99, Strand.PLUS)})
    assert diff["only_alleleforge"] == {("chr2", 10, Strand.PLUS)}
    assert diff["only_cas_offinder"] == {("chr2", 99, Strand.PLUS)}
