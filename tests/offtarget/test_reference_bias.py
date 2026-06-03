"""Reference-bias reproduction: a population variant creates a de-novo off-target.

Integration test reproducing the published reference-bias finding (Cancellieri,
Pinello et al., *Nat Genet* 2023): the BCL11A enhancer variant ``rs114518452``
creates a *de novo* ``NGG`` PAM that yields a high-CFD off-target, enriched in
African-ancestry populations. A reference-only scan is blind to it; AlleleForge's
population-aware engine nominates it and reports it ancestry-stratified.

The locus here is synthetic; the *finding* — a minor allele creating an
ancestry-enriched off-target invisible to a reference-only scan — is the point.
"""

from __future__ import annotations

from collections.abc import Callable

from alleleforge.data.gnomad import GnomadDB, PopulationFrequency
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM
from alleleforge.types.offtarget import SiteOrigin

from .conftest import PAD, SPACER

NGG = PAM(pattern="NGG")
MakeRef = Callable[[dict[str, str]], ReferenceGenome]

#: rs114518452-like allele: AFR-enriched, rare elsewhere; creates the de-novo PAM.
RS114518452 = PopulationFrequency(
    chrom="chr2",
    pos=32,
    ref="T",
    alt="G",
    overall_af=0.03,
    populations={"afr": 0.105, "amr": 0.012, "eas": 0.0, "nfe": 0.001, "sas": 0.0},
)


def test_reference_only_scan_is_blind(make_reference: MakeRef) -> None:
    # Reference protospacer is followed by 'CGT' — no NGG PAM, so no off-target.
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    assert search(SPACER, NGG, reference=ref).n_sites == 0


def test_population_aware_scan_finds_high_cfd_off_target(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    gnomad = GnomadDB([RS114518452])
    report = search(SPACER, NGG, reference=ref, gnomad=gnomad)

    assert report.n_sites == 1
    site = report.sites[0]
    assert site.origin is SiteOrigin.POPULATION
    assert site.score >= 0.20  # high-CFD: the perfect protospacer + de-novo NGG PAM
    assert site.causal_allele == "chr2:32:T>G"
    assert "afr" in site.populations
    assert site.frequency == 0.105


def test_off_target_is_ancestry_stratified(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    report = search(SPACER, NGG, reference=ref, gnomad=GnomadDB([RS114518452]))
    site = report.sites[0]

    # The site carries a per-ancestry frequency annotation; the danger is
    # concentrated in African-ancestry genomes and near-absent elsewhere.
    assert site.ancestries["afr"] == max(site.ancestries.values())
    assert site.ancestries["afr"] > site.ancestries.get("nfe", 0.0)
    assert "sas" not in site.ancestries  # below MAF in SAS -> not carried

    # The report exposes a non-empty stratification by default.
    assert report.ancestry_stratification()
    assert report.worst_ancestry() is not None
