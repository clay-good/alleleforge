"""Tests for the five-stage off-target engine."""

from __future__ import annotations

from collections.abc import Callable

from alleleforge.data.gnomad import GnomadDB, PopulationFrequency
from alleleforge.data.haplotypes import Haplotype
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import low_stringency_pam, search
from alleleforge.types.guide import PAM
from alleleforge.types.offtarget import SiteOrigin
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.types.variant import Variant

from .conftest import PAD, SPACER

NGG = PAM(pattern="NGG")
MakeRef = Callable[[dict[str, str]], ReferenceGenome]


def _pf(**kw: object) -> PopulationFrequency:
    base = {"chrom": "chr2", "pos": 32, "ref": "T", "alt": "G", "overall_af": 0.05}
    base.update(kw)
    return PopulationFrequency(**base)  # type: ignore[arg-type]


def test_low_stringency_pam_broadening() -> None:
    assert low_stringency_pam(PAM(pattern="NGG")).pattern == "NRG"
    assert low_stringency_pam(PAM(pattern="TTTV")).pattern == "TTTV"


def test_reference_on_target(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    report = search(SPACER, NGG, reference=ref)
    assert report.n_sites >= 1
    assert report.sites[0].origin is SiteOrigin.REFERENCE
    assert report.sites[0].score == 1.0
    assert report.reference_build == "hg38"


def test_report_names_scorer_and_matrix(make_reference: MakeRef) -> None:
    # The report must say which scorer + weight source produced its scores, so a
    # consumer can tell the published matrix from the transparent approximation.
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    report = search(SPACER, NGG, reference=ref)
    assert report.scorer == "CFD"
    assert report.score_matrix == "doench-2016-cfd"


def test_fm_index_reference_path_matches_linear(make_reference: MakeRef) -> None:
    """Forcing the FM-index reference path yields the same report as the scan."""
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD + SPACER[:5] + "CCC" + PAD})
    linear = search(SPACER, NGG, reference=ref, use_fm_index=False)
    indexed = search(SPACER, NGG, reference=ref, use_fm_index=True)
    assert [s.locus for s in indexed.sites] == [s.locus for s in linear.sites]
    assert indexed.n_sites == linear.n_sites


def test_population_blind_spot(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    gnomad = GnomadDB([_pf(populations={"afr": 0.10, "nfe": 0.01})])
    # Reference-only is blind to the de-novo PAM.
    assert search(SPACER, NGG, reference=ref).n_sites == 0
    # Population-aware search finds it.
    report = search(SPACER, NGG, reference=ref, gnomad=gnomad)
    assert report.n_sites == 1
    site = report.sites[0]
    assert site.origin is SiteOrigin.POPULATION
    assert "afr" in site.populations
    assert site.score == 1.0


def test_site_records_mit_score(make_reference: MakeRef) -> None:
    # An ungapped 20-nt site carries the MIT score alongside the primary CFD, so a
    # nomination retained by the engine's MIT reporting threshold (an OR with CFD)
    # is auditable even when the displayed primary score is CFD.
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    site = search(SPACER, NGG, reference=ref).sites[0]
    assert site.score_method.value == "cfd"
    assert site.mit_score == 1.0  # perfect ungapped match -> MIT 1.0, recorded not dropped


def test_thresholds_filter(make_reference: MakeRef) -> None:
    mut = SPACER[:2] + "AA" + SPACER[4:]  # two distal mismatches
    ref = make_reference({"chr2": PAD + mut + "TGG" + PAD})
    assert search(SPACER, NGG, reference=ref, cfd_threshold=0.99, mit_threshold=0.99).n_sites == 0
    assert search(SPACER, NGG, reference=ref, cfd_threshold=0.0, mit_threshold=0.0).n_sites >= 1


def test_ancestry_stratification(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    gnomad = GnomadDB([_pf(populations={"afr": 0.10, "nfe": 0.01})])
    report = search(SPACER, NGG, reference=ref, gnomad=gnomad)
    strata = report.ancestry_stratification()
    assert set(strata) == {"afr", "nfe"}  # ancestry-stratified by default
    worst = report.worst_ancestry()
    assert worst is not None and worst[1] >= 0.20
    # the per-ancestry frequency carries the differential risk signal
    assert report.sites[0].ancestries["afr"] > report.sites[0].ancestries["nfe"]


def test_haplotype_stage(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    hap = Haplotype(
        hap_id="H1",
        interval=GenomicInterval(chrom="chr2", start=10, end=40, strand=Strand.PLUS),
        variants=(Variant(chrom="chr2", pos=32, ref="T", alt="G"),),
        frequencies={"AFR": 0.2},
        source="1000g",
    )
    report = search(SPACER, NGG, reference=ref, haplotypes=[hap])
    assert report.n_sites == 1
    assert report.sites[0].origin is SiteOrigin.POPULATION


def test_patient_vcf_stage(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    report = search(
        SPACER, NGG, reference=ref, patient_vcf=[Variant(chrom="chr2", pos=32, ref="T", alt="G")]
    )
    assert report.n_sites == 1
    assert report.sites[0].origin is SiteOrigin.PATIENT


def test_region_restriction(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    empty = GenomicInterval(chrom="chr2", start=0, end=5, strand=Strand.PLUS)
    assert search(SPACER, NGG, reference=ref, regions=[empty]).n_sites == 0


def test_search_accepts_spacer_object(make_reference: MakeRef) -> None:
    from alleleforge.types.guide import Spacer
    from alleleforge.types.sequence import DNASequence

    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    report = search(Spacer(sequence=DNASequence(SPACER)), NGG, reference=ref)
    assert report.n_sites >= 1
    assert report.spacer == SPACER
