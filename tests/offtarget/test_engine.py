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


def test_on_target_excluded_but_paralog_kept(make_reference: MakeRef) -> None:
    # The reference carries the guide's own protospacer at chr2:10-30(+) (the
    # intended target) AND an identical paralog at chr2:43-63(+) (a real perfect
    # off-target). A bare scan reports both; passing the on-target locus drops
    # exactly that one site — the intended target is not an off-target, and the
    # Hsu/CRISPOR aggregate excludes it — while the paralog is retained.
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD + SPACER + "TGG" + PAD})
    on_target = GenomicInterval(chrom="chr2", start=10, end=30, strand=Strand.PLUS)

    bare = search(SPACER, NGG, reference=ref)
    assert {(s.locus.start, s.locus.end) for s in bare.sites} == {(10, 30), (43, 63)}
    assert bare.worst_score() == 1.0
    assert bare.specificity_score() == 1.0 / 3.0  # both perfect matches counted

    scoped = search(SPACER, NGG, reference=ref, on_target=on_target)
    assert {(s.locus.start, s.locus.end) for s in scoped.sites} == {(43, 63)}
    assert scoped.n_sites == 1  # only the genuine paralog remains
    assert scoped.sites[0].score == 1.0  # a paralogous perfect match is real risk
    assert scoped.specificity_score() == 0.5  # 1 / (1 + 1)


def test_on_target_match_is_naming_aware(make_reference: MakeRef) -> None:
    # The on-target locus given in the other contig-naming style still excludes
    # the self-match (the codebase reconciles chr1 vs 1 everywhere).
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    bare_named = GenomicInterval(chrom="2", start=10, end=30, strand=Strand.PLUS)
    report = search(SPACER, NGG, reference=ref, on_target=bare_named)
    assert report.n_sites == 0  # the sole site (the on-target) is excluded


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


def test_regions_scope_excludes_out_of_region_haplotype_sites(make_reference: MakeRef) -> None:
    # An explicit `regions` scope must bound *every* pass. The haplotype panel here
    # creates a site at chr2:10-30, but the caller scoped the search to a disjoint
    # window — that site must not be reported (previously the haplotype/patient
    # passes ignored `regions` and leaked out-of-scope hits).
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    hap = Haplotype(
        hap_id="H1",
        interval=GenomicInterval(chrom="chr2", start=10, end=40, strand=Strand.PLUS),
        variants=(Variant(chrom="chr2", pos=32, ref="T", alt="G"),),
        frequencies={"AFR": 0.2},
        source="1000g",
    )
    disjoint = GenomicInterval(chrom="chr2", start=40, end=43, strand=Strand.PLUS)
    scoped = search(SPACER, NGG, reference=ref, haplotypes=[hap], regions=[disjoint])
    assert scoped.n_sites == 0
    # The same haplotype site is reported when the scope covers it (proving it exists).
    covering = GenomicInterval(chrom="chr2", start=0, end=43, strand=Strand.PLUS)
    assert search(SPACER, NGG, reference=ref, haplotypes=[hap], regions=[covering]).n_sites == 1


def test_patient_vcf_stage(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    report = search(
        SPACER, NGG, reference=ref, patient_vcf=[Variant(chrom="chr2", pos=32, ref="T", alt="G")]
    )
    assert report.n_sites == 1
    assert report.sites[0].origin is SiteOrigin.PATIENT


def test_subthreshold_tail_lowers_specificity(make_reference: MakeRef) -> None:
    # A guide whose only reference off-target is sub-threshold (2 seed mismatches:
    # CFD ~0.07, MIT ~0.004, both below the reporting thresholds) reports zero sites
    # but is *not* as specific as a genuinely clean guide — the sub-threshold tail is
    # carried into the genome-wide aggregate rather than silently dropped.
    off = SPACER[:16] + "T" + "A" + SPACER[18:]  # positions 16 (A->T), 17 (C->A)
    ref = make_reference({"chr2": PAD + off + "TGG" + PAD})
    report = search(SPACER, NGG, reference=ref)
    assert report.n_sites == 0  # the tail hit does not clear either threshold
    assert report.subthreshold_score_sum > 0.0
    assert report.specificity_score() < 1.0

    clean = make_reference({"chr2": PAD + "T" * 40})  # no protospacer at all
    clean_report = search(SPACER, NGG, reference=clean)
    assert clean_report.n_sites == 0
    assert clean_report.specificity_score() == 1.0  # a truly clean guide is fully specific
    assert clean_report.specificity_score() > report.specificity_score()


def test_bulge_site_records_approximation_matrix(make_reference: MakeRef) -> None:
    # An RNA-bulge alignment collapses to 19 nt, which the published CFD matrix does
    # not cover. The site is still nominated (recall preserved) but records the
    # length-relative approximation as its matrix, so it is never mislabeled as
    # published CFD even though the report-level scorer is the published matrix.
    rna_bulge = SPACER[:10] + SPACER[11:]  # a 19-nt protospacer (one base deleted)
    ref = make_reference({"chr2": PAD + rna_bulge + "TGG" + PAD})
    report = search(SPACER, NGG, reference=ref)
    bulged = [s for s in report.sites if s.rna_bulges == 1]
    assert bulged, "expected an RNA-bulge site"
    assert bulged[0].score_matrix == "doench-2016-seed-tolerance-approximation"
    assert report.score_matrix == "doench-2016-cfd"  # report-level scorer is unchanged


def test_dna_bulge_site_records_approximation_matrix(make_reference: MakeRef) -> None:
    # A DNA-bulge alignment collapses the *target* by one base but leaves both the
    # aligned spacer and target at 20 nt, so a length-only fallback check would miss
    # it and score/label the hit as published CFD — the published matrix is 20-nt
    # *ungapped*-only, so a bulge-collapsed hit must use the length-relative
    # approximation. Regression: the fallback now keys on the hit's bulge status.
    dna_bulge = SPACER[:10] + "A" + SPACER[10:]  # 21-nt protospacer (one extra base)
    ref = make_reference({"chr2": PAD + dna_bulge + "TGG" + PAD})
    report = search(SPACER, NGG, reference=ref)
    bulged = [s for s in report.sites if s.dna_bulges == 1]
    assert bulged, "expected a DNA-bulge site"
    assert bulged[0].score_matrix == "doench-2016-seed-tolerance-approximation"
    assert bulged[0].mit_score is None  # MIT is undefined for a bulged alignment
    assert report.score_matrix == "doench-2016-cfd"  # report-level scorer is unchanged


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
