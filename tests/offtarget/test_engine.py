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
    assert inert.population_variants_considered == 0
    assert "contributed no variants in this region" in inert.search_description()

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
    assert covered.population_variants_considered == 1
    assert "contributed no variants" not in covered.search_description()

    # No source at all is a third state, not the same as "supplied and empty": the
    # existing reference-only warning covers it, and this caveat must not fire.
    none_given = search(SPACER, NGG, reference=reference)
    assert none_given.population_variants_considered is None
    assert "contributed no variants" not in none_given.search_description()
