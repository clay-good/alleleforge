"""Tests for the five-stage off-target engine."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest

from alleleforge.data.gnomad import GnomadDB, PopulationFrequency
from alleleforge.data.haplotypes import Haplotype
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import low_stringency_pam, search
from alleleforge.types.guide import PAM, Spacer
from alleleforge.types.offtarget import SiteOrigin
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand
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


def test_the_report_records_what_narrowed_it(make_reference: MakeRef) -> None:
    """A site count is not comparable between reports unless both say their cut-offs.

    The same guide yields a different number of sites at a 0.20 CFD threshold than
    at 0.05, and a bulge-free search misses a class of site entirely.
    `mismatch_threshold` was already recorded for exactly this reason; the budget
    and the reporting thresholds beside it were not, so "2 sites" could not be read
    against another report's "15".
    """
    reference = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    report = search(
        SPACER,
        NGG,
        reference=reference,
        mismatches=2,
        dna_bulges=0,
        rna_bulges=0,
        cfd_threshold=0.05,
        mit_threshold=0.01,
    )
    assert report.mismatch_threshold == 2
    assert report.dna_bulge_budget == 0
    assert report.rna_bulge_budget == 0
    assert report.cfd_threshold == 0.05
    assert report.mit_threshold == 0.01


def test_the_guide_does_not_off_target_itself_through_a_bulge(make_reference: MakeRef) -> None:
    """The on-target self-match also arrives bulged, at an interval one base short.

    The exclusion matched the placement exactly, which is right for an un-bulged hit
    — with no bulge a different start is a different protospacer. With bulges allowed
    the guide aligns to *its own locus* through one RNA bulge: same bases, zero
    mismatches, score 1.0, at an interval one base shorter than the placement. That
    survived the exact test, halving specificity to 0.5 and pegging the worst-case
    score at 1.0 for a spotless guide — on a realistic prime menu, 170 of 470
    candidates carried it.

    The window below is lifted from that reproduction rather than invented, because a
    synthetic sequence does not reliably admit a bulged self-alignment and the test
    then passes against the bug.
    """
    window = "GAGCCGGATAAGTCTGCCGTTACTGCCCTGTTGGAATGACATGCACGTTATTCTTTTTACGCAGCGTTTTGCTTGATCGG"
    spacer = "ACGTGCATGTCATTCCAACA"
    reference = make_reference({"chr11": window})
    # Placement of the spacer's own protospacer within the window (minus strand).
    locus = GenomicInterval(chrom="chr11", start=28, end=48, strand=Strand.MINUS)

    unexcluded = search(spacer, NGG, reference=reference, mismatches=2, dna_bulges=1, rna_bulges=1)
    bulged_self = [s for s in unexcluded.sites if s.score >= 1.0 and (s.dna_bulges or s.rna_bulges)]
    assert bulged_self, "fixture no longer produces a bulged self-match — the test is vacuous"

    report = search(
        spacer,
        NGG,
        reference=reference,
        mismatches=2,
        dna_bulges=1,
        rna_bulges=1,
        on_target=locus,
    )
    assert all(site.score < 1.0 for site in report.sites), (
        f"self-match survived: {[(str(s.locus), s.score) for s in report.sites if s.score >= 1.0]}"
    )
    assert report.specificity_score() > unexcluded.specificity_score()


def test_the_widened_exclusion_does_not_swallow_a_bulged_neighbour(
    make_reference: MakeRef,
) -> None:
    """Only hits *inside* the placement window are the guide itself.

    The fix widens the exclusion for bulged hits, and a widening that excluded every
    bulged hit would "pass" the test above while being far worse than the bug. A
    bulged hit at another locus must still be reported.
    """
    window = "GAGCCGGATAAGTCTGCCGTTACTGCCCTGTTGGAATGACATGCACGTTATTCTTTTTACGCAGCGTTTTGCTTGATCGG"
    spacer = "ACGTGCATGTCATTCCAACA"
    # A second copy of the same locus far downstream: its bulged alignment is a real
    # off-target, outside the on-target window, and must survive the exclusion.
    reference = make_reference({"chr11": window + "T" * 40 + window})
    locus = GenomicInterval(chrom="chr11", start=28, end=48, strand=Strand.MINUS)
    report = search(
        spacer,
        NGG,
        reference=reference,
        mismatches=2,
        dna_bulges=1,
        rna_bulges=1,
        on_target=locus,
    )
    far = [s for s in report.sites if s.locus.start > 100]
    assert far, f"the distant copy was swallowed; kept {[str(s.locus) for s in report.sites]}"
    assert any(s.score >= 1.0 for s in far), "the distant perfect match lost its score"


def test_only_hits_inside_the_placement_window_count_as_the_guide_itself() -> None:
    """The containment predicate, tested directly — the end-to-end tests cannot reach it.

    A bulged self-match is excluded by *containment* in the placement grown by the
    bulge budget, and the failure mode of that widening is excluding a real bulged
    off-target elsewhere. Only a bulged hit can exercise it, and constructing a
    genomic fixture whose distant off-target appears *solely* as a bulged alignment is
    unreliable — so the predicate is exercised here on synthetic hits instead.
    """
    from alleleforge.offtarget._search import Hit
    from alleleforge.offtarget.engine import _is_on_target

    locus = GenomicInterval(chrom="chr1", start=100, end=120, strand=Strand.PLUS)

    def _hit(start: int, end: int, *, rna: int = 1, strand: Strand = Strand.PLUS) -> Hit:
        return Hit(
            chrom="chr1",
            start=start,
            end=end,
            strand=strand,
            pam_sequence="TGG",
            aligned_spacer="A" * 19,
            aligned_target="A" * 19,
            mismatches=0,
            dna_bulges=0,
            rna_bulges=rna,
        )

    assert _is_on_target(_hit(101, 120), locus)  # the real case: one base short
    assert _is_on_target(_hit(100, 119), locus)  # ...and short at the other end
    assert _is_on_target(_hit(99, 121), locus)  # one base of slack on each side

    # Outside the window: a genuine bulged off-target that must be reported.
    assert not _is_on_target(_hit(98, 120), locus)
    assert not _is_on_target(_hit(100, 122), locus)
    assert not _is_on_target(_hit(500, 520), locus)
    # ...and the original guarantees are untouched.
    assert not _is_on_target(_hit(101, 120, strand=Strand.MINUS), locus)
    assert not _is_on_target(_hit(101, 121, rna=0), locus)  # no bulge: a different site
    assert _is_on_target(_hit(100, 120, rna=0), locus)  # exact match, bulge or not
    assert not _is_on_target(_hit(101, 120), None)


def test_a_site_records_the_pam_that_anchored_it(make_reference: MakeRef) -> None:
    """Without the PAM an off-target row cannot be interpreted or told apart.

    Two things were undecidable from a report. A canonical `NGG` site and a
    low-stringency `NAG` one carry very different real risk and looked identical. And
    with bulges allowed the same 20 bp of genome is reachable from two *adjacent*
    PAMs, so a table showed what appeared to be one locus printed twice — it is in
    fact two distinct cut registers, which only the PAM reveals.
    """
    window = "GAGCCGGATAAGTCTGCCGTTACTGCCCTGTTGGAATGACATGCACGTTATTCTTTTTACGCAGCGTTTTGCTTGATCGG"
    reference = make_reference({"chr11": window})
    report = search(
        "ACGTGCATGTCATTCCAACA",
        NGG,
        reference=reference,
        mismatches=3,
        dna_bulges=1,
        rna_bulges=1,
    )
    assert all(site.pam_sequence for site in report.sites)
    assert all(NGG.matches(site.pam_sequence or "") for site in report.sites)

    # The two overlapping registers are distinguished by their PAMs, not merged: they
    # are one base apart with different PAMs, so each is a real, separate cut site.
    overlapping = [s for s in report.sites if s.score >= 1.0]
    assert len(overlapping) == 2
    assert len({s.pam_sequence for s in overlapping}) == 2, (
        "overlapping registers share a PAM — then they would be one site reported twice"
    )


def test_a_scan_says_how_much_of_the_region_was_searchable(make_reference: MakeRef) -> None:
    """ "0 sites" over a region that is mostly assembly gap is not a clean bill.

    A window holding an `N` run or an IUPAC code cannot be scanned, and the report
    looked identical either way — so a search restricted to a region overlapping a
    centromere or a scaffold gap examined almost nothing and said what a search over
    fully-resolved sequence says.
    """
    gappy = make_reference({"chr2": PAD + SPACER + "TGG" + "N" * 4000})
    report = search(SPACER, NGG, reference=gappy)

    assert report.searched_bases == len(PAD) + len(SPACER) + 3 + 4000
    assert report.resolved_bases == report.searched_bases - 4000
    assert "were searchable" in report.search_description()
    assert "1% of the" in report.search_description()

    # A fully-resolved reference says nothing about coverage: a caveat on every report
    # is furniture, and a scattered ambiguity code is not news.
    clean = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    clean_report = search(SPACER, NGG, reference=clean)
    assert clean_report.resolved_bases == clean_report.searched_bases
    assert "searchable" not in clean_report.search_description()


def test_a_region_running_past_a_contig_end_is_not_called_an_assembly_gap(
    make_reference: MakeRef,
) -> None:
    """A fetch pads past the contig end, and that padding is not a gap.

    Found while validating region panels: a region overlapping the end of a short
    contig came back "only 88% searchable (the rest are assembly gaps or ambiguity
    codes)". The fraction was right and the explanation was not — nothing is missing
    from the assembly there, the region simply asked for more than the contig has.
    """
    contig = PAD + SPACER + "TGG" + PAD
    reference = make_reference({"chr2": contig})
    over = GenomicInterval(chrom="chr2", start=0, end=len(contig) + 20, strand=Strand.PLUS)
    report = search(SPACER, NGG, reference=reference, regions=[over])
    assert report.resolved_bases < report.searched_bases
    assert "past a contig end" in report.search_description()


def test_an_ambiguity_code_counts_against_the_searchable_fraction(
    make_reference: MakeRef,
) -> None:
    """Not only `N`: a real FASTA carries R/Y/S/W codes, and those are unscannable too."""
    coded = make_reference({"chr2": PAD + SPACER + "TGG" + "R" * 200 + PAD})
    report = search(SPACER, NGG, reference=coded)
    assert report.resolved_bases == report.searched_bases - 200
    assert "were searchable" in report.search_description()


def test_a_population_source_that_covers_nothing_here_says_so(make_reference: MakeRef) -> None:
    """A supplied-but-inert frequency file is the more dangerous of the two cases.

    The warning for a *missing* population source has existed for a while. A source
    that is present and contributes nothing in the searched region produced no warning
    at all — and the resulting empty ancestry breakdown is byte-identical to a
    genuinely clean one, while the user believes they did it right. A per-chromosome
    download, a region subset or a filtered slice all land here.
    """
    reference = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})

    # A perfectly valid frequency source — for a locus this search never touches.
    elsewhere = GnomadDB(
        [_pf(chrom="chr9", pos=1000, ref="A", alt="G", overall_af=0.08, populations={"afr": 0.1})]
    )
    inert = search(SPACER, NGG, reference=reference, gnomad=elsewhere, populations=("afr",))
    assert inert.sources_considered == {"gnomad": 0}
    assert "supplied but contributing nothing in this region: gnomad" in (
        inert.search_description()
    )

    # A source that does cover the region says nothing: the caveat tracks the data.
    here = GnomadDB(
        [
            _pf(
                chrom="chr2",
                pos=len(PAD) + len(SPACER) + 1,
                ref="G",
                alt="A",
                overall_af=0.08,
                populations={"afr": 0.1},
            )
        ]
    )
    covered = search(SPACER, NGG, reference=reference, gnomad=here, populations=("afr",))
    assert covered.sources_considered == {"gnomad": 1}
    assert "contributing nothing" not in covered.search_description()

    # No source at all is a third state, not the same as "supplied and empty": the
    # existing reference-only warning covers it, and this caveat must not fire.
    none_given = search(SPACER, NGG, reference=reference)
    assert none_given.sources_considered == {}  # absent, not zero
    assert "contributing nothing" not in none_given.search_description()


def test_every_supplied_safety_source_gets_the_same_coverage_check(
    make_reference: MakeRef,
) -> None:
    """gnomAD was checked and the other two were not — the shape this audit keeps finding.

    A haplotype panel or a patient VCF for another locus is exactly as inert as a
    gnomAD file for another locus, and produces exactly the same empty ancestry
    breakdown. Checking one source and not its siblings is how the gap arose.
    """
    reference = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    elsewhere = Variant(chrom="chr9", pos=5000, ref="A", alt="G", build="hg38")
    here = Variant(chrom="chr2", pos=len(PAD) + 2, ref=SPACER[2], alt="G", build="hg38")

    inert = search(
        SPACER,
        NGG,
        reference=reference,
        haplotypes=[
            Haplotype(
                hap_id="h1",
                interval=GenomicInterval(chrom="chr9", start=4990, end=5010, strand=Strand.PLUS),
                variants=(elsewhere,),
                frequencies={"afr": 0.2},
                source="1000g",
            )
        ],
        patient_vcf=[elsewhere],
        populations=("afr",),
    )
    assert inert.sources_considered == {"haplotypes": 0, "patient-vcf": 0}
    described = inert.search_description()
    assert "haplotypes" in described and "patient-vcf" in described

    covering = search(
        SPACER,
        NGG,
        reference=reference,
        haplotypes=[
            Haplotype(
                hap_id="h1",
                interval=GenomicInterval(chrom="chr2", start=10, end=40, strand=Strand.PLUS),
                variants=(here,),
                frequencies={"afr": 0.2},
                source="1000g",
            )
        ],
        patient_vcf=[here],
        populations=("afr",),
    )
    assert covering.sources_considered == {"haplotypes": 1, "patient-vcf": 1}
    assert "contributing nothing" not in covering.search_description()


def test_an_ancestry_with_no_data_behind_it_is_named(make_reference: MakeRef) -> None:
    """Asking to stratify by an ancestry the source has no column for is dropped silently.

    Provenance records it among the populations considered, so the artifact asserts an
    ancestry was examined when nothing for it exists — and its absence from the
    breakdown reads as "no risk in that population" rather than "no data". Distinct
    from requesting ancestries with no source at all, which is warned separately.
    """
    reference = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    db = GnomadDB(
        [
            _pf(
                chrom="chr2",
                pos=len(PAD) + 2,
                ref=SPACER[2],
                alt="C",
                overall_af=0.08,
                populations={"afr": 0.12, "nfe": 0.001},
            )
        ]
    )

    partial = search(SPACER, NGG, reference=reference, gnomad=db, populations=("afr", "sas"))
    assert partial.unbacked_populations == ("sas",)
    assert "no supplied source carries data for sas" in partial.search_description()

    # Every request backed: nothing said, or the caveat is furniture.
    backed = search(SPACER, NGG, reference=reference, gnomad=db, populations=("afr", "nfe"))
    assert backed.unbacked_populations == ()
    assert "no supplied source carries data" not in backed.search_description()

    # A haplotype panel backs its own ancestries, so the check spans every source.
    panel = Haplotype(
        hap_id="h1",
        interval=GenomicInterval(chrom="chr2", start=10, end=40, strand=Strand.PLUS),
        variants=(Variant(chrom="chr2", pos=len(PAD) + 2, ref=SPACER[2], alt="C"),),
        frequencies={"sas": 0.3},
        source="1000g",
    )
    both = search(
        SPACER, NGG, reference=reference, gnomad=db, haplotypes=[panel], populations=("afr", "sas")
    )
    assert both.unbacked_populations == ()

    # With no source at all this stays empty: that case has its own warning, and two
    # warnings for one situation is worse than one.
    none_given = search(SPACER, NGG, reference=reference, populations=("afr", "sas"))
    assert none_given.unbacked_populations == ()


def test_a_search_over_no_sequence_says_so(make_reference: MakeRef) -> None:
    """An empty search returns the most reassuring report the system can produce.

    A truncated reference — a contig header with no bases, i.e. an interrupted
    download — indexes without complaint and yields "0 sites, worst score 0.000,
    specificity 1.000". Every number is correct and the conclusion a reader draws is
    the opposite of the truth. The searchable-fraction line does not fire either,
    because there were no requested bases to take a fraction of.
    """
    empty = make_reference({"chr1": ""})
    report = search(SPACER, NGG, reference=empty)

    assert report.n_sites == 0
    assert report.specificity_score() == 1.0  # arithmetically right, and meaningless
    assert report.searched_bases == 0
    assert "NO SEQUENCE WAS SEARCHED" in report.search_description()

    # A real search says nothing of the kind.
    real = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    assert "NO SEQUENCE" not in search(SPACER, NGG, reference=real).search_description()


def test_an_ambiguous_spacer_position_is_named_because_it_biases_scores_low(
    make_reference: MakeRef,
) -> None:
    """An unscoreable position pushes the score toward 0 — the reassuring direction.

    The CFD matrix has no entry for a non-ACGT base, so the aligner counts it as a
    mismatch and the site's score falls. On a safety axis that is exactly backwards:
    the real base is unknown and may match perfectly, so an ambiguous position should
    make a reader *less* confident and instead made the number look better. A
    degenerate spacer is a legitimate reagent — the oligo layer says so — so this is
    recorded rather than refused.
    """
    reference = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    degenerate = SPACER[:-1] + "N"

    report = search(degenerate, NGG, reference=reference)
    assert report.ambiguous_spacer_positions == (len(SPACER),)
    described = report.search_description()
    assert "ambiguous at position(s) 20" in described
    assert "not evidence of safety" in described

    # The bias is real, not hypothetical: the same locus scores lower with the
    # ambiguous base than with the concrete one it stands in for.
    concrete = search(SPACER, NGG, reference=reference)
    assert concrete.worst_score() > report.worst_score()

    # A concrete spacer says nothing, or the caveat is furniture.
    assert concrete.ambiguous_spacer_positions == ()
    assert "ambiguous at position" not in concrete.search_description()


def test_the_searchable_count_handles_soft_masked_sequence(make_reference: MakeRef) -> None:
    """Lowercase bases are sequence, not gaps — a repeat-masked FASTA is the normal case.

    The searchable-base count avoids an `upper()` copy of the region — a ~250 MB
    transient on a whole chromosome, in a path whose design is explicitly
    bounded-memory — and is correct only because `ReferenceGenome.fetch` normalizes
    case on the way out. This pins that end-to-end guarantee, which is what the count
    relies on and which no test in the counting module can express.
    """
    masked = (PAD + SPACER + "TGG").lower() + PAD
    reference = make_reference({"chr2": masked})
    report = search(SPACER, NGG, reference=reference)

    assert report.resolved_bases == report.searched_bases == len(masked)
    assert "were searchable" not in report.search_description()
    # ...and the scan itself still finds the site through the soft-masking.
    assert report.n_sites == 1


def test_the_searchable_count_does_not_depend_on_a_dependency_default() -> None:
    """Sequence arrives upper-cased today because of a pyfaidx option, not an invariant.

    `ReferenceGenome` constructs `Fasta(..., sequence_always_upper=True)`, so a
    repeat-masked genome is normalized before the count sees it. That is a *dependency
    default*: if it changed, every base of a soft-masked chromosome would count as
    unsearchable and the report would claim a real scan had covered almost nothing —
    the exact false alarm inverse to the one the count exists to prevent. The counter
    is therefore case-insensitive, and this pins it directly rather than through a
    reference whose normalization would mask the difference.
    """
    from alleleforge.offtarget.engine import _resolved_base_count

    # The engine's own counter, not a copy of its expression: an inline version could
    # only be tested by restating it, which passes whatever the engine does.
    assert _resolved_base_count("acgtacgtNN") == 8
    assert _resolved_base_count("ACGTACGTNN") == 8
    assert _resolved_base_count("acgtACGT") == 8
    assert _resolved_base_count("NNNN") == 0
    assert _resolved_base_count("") == 0
    # Ambiguity codes are unsearchable in either case.
    assert _resolved_base_count("ryswkm" + "RYSWKM") == 0


def test_a_one_shot_patient_iterable_is_not_consumed_twice(make_reference: MakeRef) -> None:
    """`patient_vcf` is typed `Iterable` and was read twice, losing the second pass.

    The two passes are the region-coverage count and the enumeration that actually
    personalizes the search. With a generator the *second* one got nothing — so the
    count reported that patient data had been used while none of it was, which is the
    inverted, silent failure this project keeps looking for. Haplotypes were already
    materialized; this was the sibling that was not.
    """
    reference = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    variant = Variant(chrom="chr2", pos=len(PAD) + 2, ref=SPACER[2], alt="C", build="hg38")

    class _OneShot:
        """Iterable exactly once, like a generator, and counts the attempts."""

        def __init__(self, items: list[Variant]) -> None:
            self.passes = 0
            self._iterator = iter(items)

        def __iter__(self) -> Iterator[Variant]:
            self.passes += 1
            return self._iterator

    one_shot = _OneShot([variant])
    report = search(SPACER, NGG, reference=reference, patient_vcf=one_shot)
    assert one_shot.passes == 1
    assert report.sources_considered == {"patient-vcf": 1}

    # A re-iterable caller is unaffected: the engine copies internally, and the
    # provenance carrier the CLI passes (`_PatientVariants`, a list subclass with a
    # `dataset_version` attribute) is the caller's own object throughout.
    reusable = [variant]
    first = search(SPACER, NGG, reference=reference, patient_vcf=reusable)
    second = search(SPACER, NGG, reference=reference, patient_vcf=reusable)
    assert first.sources_considered == second.sources_considered == {"patient-vcf": 1}
    assert len(reusable) == 1


def test_search_refuses_a_scorer_that_cannot_serve_the_budget(make_reference: MakeRef) -> None:
    """The guard belonged in `search()`, not in the CLI.

    The MIT score is defined only for an ungapped 20-nt alignment, so a bulge budget
    makes it raise partway through the scan with a message about the *alignment*
    length — which reads as a complaint about the caller's spacer, and the caller's
    spacer is fine. The refusal was added to the CLI first, so the library, the cohort
    path and any future web caller still hit the deep failure. Every caller passes
    through `search`.
    """
    from alleleforge.offtarget.scoring import MitScorer

    reference = make_reference({"chr1": "T" * 20 + "TTTAAACGTTTTTTTTTTTT" + "TGG" + "T" * 20})
    spacer = Spacer(sequence=DNASequence("TTTAAACGTTTTTTTTTTTT"))

    with pytest.raises(ValueError, match="undefined for bulged alignments"):
        search(spacer, PAM(pattern="NGG"), reference=reference, scorer=MitScorer(), dna_bulges=1)
    with pytest.raises(ValueError, match="undefined for bulged alignments"):
        search(spacer, PAM(pattern="NGG"), reference=reference, scorer=MitScorer(), rna_bulges=1)

    # ...and the combination it *can* serve is not refused.
    report = search(
        spacer,
        PAM(pattern="NGG"),
        reference=reference,
        scorer=MitScorer(),
        dna_bulges=0,
        rna_bulges=0,
    )
    assert report.scorer == "MIT"


def test_search_rejects_a_region_the_reference_cannot_serve(make_reference: MakeRef) -> None:
    """The CLI validated regions and the library did not.

    A panel built against another assembly or naming convention is the ordinary way
    this happens, and from the library it surfaced as a bare `KeyError: "unknown contig
    'chrNOPE'"` from deep inside the fetch — while the CLI, for the same mistake, said
    which contig, which the reference has, and that a dropped region searches less than
    was asked for. One of three callers got an answer they could act on.
    """
    reference = make_reference({"chr1": "ACGT" * 60})
    spacer = Spacer(sequence=DNASequence("TTTAAACGTTTTTTTTTTTT"))
    bad = GenomicInterval(chrom="chrNOPE", start=0, end=100, strand=Strand.PLUS)

    with pytest.raises(ValueError) as excinfo:
        search(spacer, PAM(pattern="NGG"), reference=reference, regions=[bad])
    message = str(excinfo.value)
    assert "chrNOPE" in message  # names the offender
    assert "chr1" in message  # ...and what the reference actually has
    assert "searches less than you asked for" in message  # ...and why it matters

    # A region the reference *can* serve is not refused.
    good = GenomicInterval(chrom="chr1", start=0, end=100, strand=Strand.PLUS)
    assert search(spacer, PAM(pattern="NGG"), reference=reference, regions=[good]) is not None


def test_the_cli_pre_check_refuses_the_same_regions(make_reference: MakeRef) -> None:
    """The CLI keeps an early exit; it must enforce the engine's rule, not its own.

    Asserted by behaviour rather than by grepping the source for the helper's name —
    the first version of this test did that, and left the call replaced by `pass`
    while still passing, because the import line kept the name in the source.
    """
    import typer

    from alleleforge.cli.main import _validate_regions

    reference = make_reference({"chr1": "ACGT" * 60})
    bad = GenomicInterval(chrom="chrNOPE", start=0, end=100, strand=Strand.PLUS)
    good = GenomicInterval(chrom="chr1", start=0, end=100, strand=Strand.PLUS)

    with pytest.raises(typer.Exit):
        _validate_regions([bad], reference)
    _validate_regions([good], reference)  # must not raise
    _validate_regions(None, reference)
