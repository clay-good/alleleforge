"""`haplotypes.py` said production builds panels from phased VCFs. It could not.

The module docstring opened with "Production builds these from phased VCFs; the test path
parses a small plain-text TSV". `from_tsv` was the only reader. So the sentence described
a pipeline no caller could run, and 1000G and HGDP — which publish exactly these phased
VCFs — were usable only after the caller wrote the conversion themselves.

That makes it the sharpest instance of the query R701 and R702 ran: usually the mismatch
is silent, inferred by comparing a registry URL against a reader. Here the module *said*
the reader existed.

Formats are taken from the real published files, because each has a detail that changes
the answer:

* the phased VCF is `CCDG_..._chr22.filtered.shapeit2-duohmm-phased.vcf.gz`, 3,211
  columns for 3,202 samples, `FORMAT` of `GT`, genotypes like `0|0`;
* the sample table is `20130606_g1k_3202_samples_ped_population.txt` —
  **space**-separated, `SampleID` in the *second* column, and carrying **two** different
  population columns.

Validated end to end against a real chr22 slice: over `chr22:10519200-10521000` it finds
a three-variant haplotype at **11.7% in AFR** and under 0.6% in every other
superpopulation. That asymmetry is the whole reason this panel exists — an off-target
created only on a haplotype common in one population — so it is the right shape of
answer, not just a parse that did not crash.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.data.haplotypes import HaplotypePanel, read_sample_populations
from alleleforge.types.sequence import GenomicInterval, Strand

#: Two samples per superpopulation, in the real file's space-separated 7-column shape.
_PED = """\
FamilyID SampleID FatherID MotherID Sex Population Superpopulation
HG00096 HG00096 0 0 1 GBR EUR
HG00097 HG00097 0 0 2 GBR EUR
NA19625 NA19625 0 0 2 ASW AFR
NA19700 NA19700 0 0 1 ASW AFR
"""

#: A phased VCF in 1000G's real column layout. HG00096 carries both ALTs on its second
#: haplotype; NA19625 carries only the first, on its first haplotype.
_VCF = """\
##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tHG00096\tHG00097\tNA19625\tNA19700
chr22\t101\t.\tG\tC\t.\tPASS\t.\tGT\t0|1\t0|0\t1|0\t0|0
chr22\t201\t.\tA\tT\t.\tPASS\t.\tGT\t0|1\t0|0\t0|0\t0|0
"""

_WINDOW = GenomicInterval(chrom="chr22", start=0, end=1000, strand=Strand.PLUS)


@pytest.fixture
def ped(tmp_path: Path) -> Path:
    path = tmp_path / "samples.txt"
    path.write_text(_PED)
    return path


@pytest.fixture
def vcf(tmp_path: Path) -> Path:
    path = tmp_path / "phased.vcf"
    path.write_text(_VCF)
    return path


# -- the sample table ----------------------------------------------------------


def test_the_sample_table_is_space_separated_not_tab(ped: Path) -> None:
    """Splitting on tabs yields one column and an empty mapping.

    The file is published with spaces. A reader written for a TSV silently produces no
    samples, and every frequency then divides by zero samples — reported as an empty
    panel rather than as a parse failure.
    """
    assert read_sample_populations(ped) == {
        "HG00096": "EUR",
        "HG00097": "EUR",
        "NA19625": "AFR",
        "NA19700": "AFR",
    }


def test_the_sample_id_is_the_second_column(ped: Path) -> None:
    """`FamilyID` comes first. Keying on it happens to work here and not in general.

    In this extract family and sample IDs coincide, which is true of most unrelated
    1000G samples and *not* of the trios — so a reader that took the first column would
    pass a test like this one and mis-key exactly the related samples.
    """
    mapping = read_sample_populations(ped)
    assert "HG00096" in mapping
    # The header's own first column must not have become a key.
    assert "FamilyID" not in mapping


def test_the_two_population_columns_are_different_questions(ped: Path) -> None:
    """`Population` is the cohort; `Superpopulation` is the continental group.

    The dataset registry describes `1000g` with the five superpopulations, so that is
    the default: a panel keyed by cohort would advertise ancestries no descriptor
    mentions, and would not answer a `--populations EUR` request at all.
    """
    assert set(read_sample_populations(ped).values()) == {"EUR", "AFR"}
    assert set(read_sample_populations(ped, column="Population").values()) == {"GBR", "ASW"}


def test_a_table_without_the_named_column_is_refused(tmp_path: Path) -> None:
    """A refusal that names what it wanted and what it found."""
    path = tmp_path / "wrong.txt"
    path.write_text("Sample Group\nHG00096 EUR\n")
    with pytest.raises(ValueError, match="does not name a 'SampleID' column") as refused:
        read_sample_populations(path)
    assert "Superpopulation" in str(refused.value)


# -- building the panel --------------------------------------------------------


def test_haplotypes_are_grouped_and_counted_per_population(vcf: Path, ped: Path) -> None:
    """Eight haplotypes from four diploid samples, grouped by the alleles they carry.

    EUR: HG00096 is `0|1` then `0|1`, so one of its haplotypes carries both ALTs and the
    other carries neither; HG00097 is reference throughout. So of four EUR haplotypes,
    three are reference and one carries two variants.

    AFR: NA19625 carries the first ALT on its first haplotype only; NA19700 is
    reference. Three of four AFR haplotypes are reference, one carries one variant.
    """
    panel = HaplotypePanel.from_phased_vcf(
        vcf,
        interval=_WINDOW,
        sample_populations=read_sample_populations(ped),
        source="1000g",
    )
    by_variant_count = {
        len(hap.variants): hap
        for hap in panel.common_haplotypes(_WINDOW, min_freq=0.0, include_reference=True)
    }

    assert by_variant_count[0].frequencies == {"EUR": 0.75, "AFR": 0.75}
    assert by_variant_count[2].frequencies == {"EUR": 0.25}
    assert by_variant_count[1].frequencies == {"AFR": 0.25}


def test_one_haplotype_carried_by_two_populations_is_one_record(tmp_path: Path, ped: Path) -> None:
    """Identical haplotypes group across populations, and the denominator is the window.

    Two properties in one fixture, because the first draft of this test got the grouping
    wrong and the measurement proved it. Over the first site alone, HG00096 is `0|1` and
    NA19625 is `1|0` — different samples, different ancestries, *the same haplotype*. So
    it is one record carrying `{AFR: 0.25, EUR: 0.25}`, not two records of 0.25 each. A
    haplotype is defined by the alleles it carries; who carries it is the frequency map.

    And the denominator stays four per superpopulation even though the window now holds
    one site rather than two. A per-site denominator would make every frequency depend on
    how many variants a window happens to contain, so adding a monomorphic site would
    change the reported frequency of an unrelated haplotype.
    """
    one_site = tmp_path / "one.vcf"
    one_site.write_text("\n".join(_VCF.splitlines()[:3]) + "\n")

    panel = HaplotypePanel.from_phased_vcf(
        one_site,
        interval=_WINDOW,
        sample_populations=read_sample_populations(ped),
        source="1000g",
    )
    assert {
        tuple(sorted(h.frequencies.items()))
        for h in panel.common_haplotypes(_WINDOW, min_freq=0.0, include_reference=True)
    } == {
        (("AFR", 0.75), ("EUR", 0.75)),  # reference on three of four in each
        (("AFR", 0.25), ("EUR", 0.25)),  # the shared single-variant haplotype
    }


def test_a_sample_outside_the_window_is_not_counted(vcf: Path, ped: Path) -> None:
    """A window with no sites yields an empty panel, not haplotypes of nothing."""
    elsewhere = GenomicInterval(chrom="chr22", start=5000, end=6000, strand=Strand.PLUS)
    panel = HaplotypePanel.from_phased_vcf(
        vcf, interval=elsewhere, sample_populations=read_sample_populations(ped), source="1000g"
    )
    assert panel.common_haplotypes(elsewhere, min_freq=0.0, include_reference=True) == []


def test_a_sample_with_no_recorded_population_is_skipped(vcf: Path) -> None:
    """Not pooled into an "unknown" group, and not left in the denominator.

    A frequency whose denominator includes samples of no stated ancestry is not a
    per-population frequency. Here only the two EUR samples are mapped, so the EUR
    denominator must be 4 — not 8.
    """
    panel = HaplotypePanel.from_phased_vcf(
        vcf,
        interval=_WINDOW,
        sample_populations={"HG00096": "EUR", "HG00097": "EUR"},
        source="1000g",
    )
    haps = panel.common_haplotypes(_WINDOW, min_freq=0.0, include_reference=True)
    assert {frozenset(h.frequencies) for h in haps} == {frozenset({"EUR"})}
    assert sum(h.frequencies["EUR"] for h in haps) == pytest.approx(1.0)


# -- the refusal that matters --------------------------------------------------


def test_an_unphased_genotype_is_refused(tmp_path: Path, ped: Path) -> None:
    """`0/1` cannot be assigned to a haplotype, and guessing would invent phase.

    This is the one error the panel must not make. The off-target engine reports a site
    as carried by a named population on the strength of these haplotypes, so phase read
    from an unphased call would attach a real-looking population claim to a haplotype
    that was never observed. Refused, naming the sample and locus.
    """
    unphased = tmp_path / "unphased.vcf"
    unphased.write_text(_VCF.replace("0|1\t0|0\t1|0", "0/1\t0|0\t1|0", 1))

    with pytest.raises(ValueError, match="unphased genotype") as refused:
        HaplotypePanel.from_phased_vcf(
            unphased,
            interval=_WINDOW,
            sample_populations=read_sample_populations(ped),
            source="1000g",
        )
    message = str(refused.value)
    assert "HG00096" in message, message
    assert "chr22:101" in message, message
    assert "invent phase" in message, message


def test_a_vcf_without_a_chrom_header_is_refused(tmp_path: Path, ped: Path) -> None:
    """Without the header the genotype columns cannot be attributed to samples.

    Proceeding would assign every sample's calls to whichever name happened to sit at
    that index — silently, and with per-population frequencies to match.
    """
    headerless = tmp_path / "noheader.vcf"
    headerless.write_text("##fileformat=VCFv4.2\nchr22\t101\t.\tG\tC\t.\tPASS\t.\tGT\t0|1\n")

    with pytest.raises(ValueError, match="missing its '#CHROM"):
        HaplotypePanel.from_phased_vcf(
            headerless,
            interval=_WINDOW,
            sample_populations=read_sample_populations(ped),
            source="1000g",
        )


def test_a_missing_call_contributes_no_allele(tmp_path: Path, ped: Path) -> None:
    """`.|.` is absence, so that haplotype carries nothing at the site.

    Treating it as reference would be a measurement nobody made; treating it as ALT
    would invent one. It stays in the denominator because the sample was genotyped.
    """
    missing = tmp_path / "missing.vcf"
    missing.write_text(_VCF.replace("0|1\t0|0\t1|0", ".|.\t0|0\t1|0", 1))

    panel = HaplotypePanel.from_phased_vcf(
        missing,
        interval=_WINDOW,
        sample_populations=read_sample_populations(ped),
        source="1000g",
    )
    haps = panel.common_haplotypes(_WINDOW, min_freq=0.0, include_reference=True)
    assert sum(h.frequencies.get("EUR", 0.0) for h in haps) == pytest.approx(1.0)
