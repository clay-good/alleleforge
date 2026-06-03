"""Tests for population-variant off-target augmentation."""

from __future__ import annotations

from collections.abc import Callable

from alleleforge.data.gnomad import PopulationFrequency
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.population import enumerate_patient_sites, enumerate_population_sites
from alleleforge.types.guide import PAM
from alleleforge.types.offtarget import SiteOrigin
from alleleforge.types.variant import Variant

from .conftest import PAD, SPACER

NRG = PAM(pattern="NRG")
MakeRef = Callable[[dict[str, str]], ReferenceGenome]


def test_de_novo_pam_creation(make_reference: MakeRef) -> None:
    # Reference has no PAM (CGT); a T->G at the PAM's 3rd base creates CGG.
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    pf = PopulationFrequency(
        chrom="chr2",
        pos=32,
        ref="T",
        alt="G",
        overall_af=0.05,
        populations={"afr": 0.10, "nfe": 0.01},
    )
    sites = enumerate_population_sites(SPACER, NRG, reference=ref, variants=[pf], maf=0.001)
    assert len(sites) == 1
    hit, prov = sites[0]
    assert (hit.start, hit.end) == (10, 30)
    assert hit.mismatches == 0
    assert prov.origin is SiteOrigin.POPULATION
    assert prov.causal_allele == "chr2:32:T>G"
    assert prov.populations == ("afr", "nfe")
    assert prov.frequency == 0.10


def test_maf_filter_excludes_rare_variant(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    pf = PopulationFrequency(
        chrom="chr2",
        pos=32,
        ref="T",
        alt="G",
        overall_af=0.0001,
        populations={"afr": 0.0001},
    )
    assert enumerate_population_sites(SPACER, NRG, reference=ref, variants=[pf], maf=0.001) == []


def test_variant_that_creates_nothing_is_silent(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    # A->G well away from any protospacer/PAM: creates no site.
    pf = PopulationFrequency(
        chrom="chr2", pos=2, ref="T", alt="G", overall_af=0.2, populations={"afr": 0.2}
    )
    assert enumerate_population_sites(SPACER, NRG, reference=ref, variants=[pf], maf=0.001) == []


def test_variant_strengthens_existing_site(make_reference: MakeRef) -> None:
    # Reference site has a single mismatch at protospacer position 5; the variant
    # restores it, dropping the edit count -> a strengthened population site.
    mutated = SPACER[:5] + ("A" if SPACER[5] != "A" else "C") + SPACER[6:]
    ref = make_reference({"chr2": PAD + mutated + "TGG" + PAD})
    pf = PopulationFrequency(
        chrom="chr2",
        pos=15,
        ref=mutated[5],
        alt=SPACER[5],
        overall_af=0.05,
        populations={"eas": 0.05},
    )
    sites = enumerate_population_sites(SPACER, NRG, reference=ref, variants=[pf], maf=0.001)
    assert len(sites) == 1
    hit, _ = sites[0]
    assert hit.mismatches == 0


def test_absent_contig_is_skipped(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    pf = PopulationFrequency(
        chrom="chrX", pos=5, ref="A", alt="G", overall_af=0.2, populations={"afr": 0.2}
    )
    assert enumerate_population_sites(SPACER, NRG, reference=ref, variants=[pf], maf=0.001) == []


def test_ref_mismatch_is_skipped(make_reference: MakeRef) -> None:
    # The variant asserts ref 'A' but the build has 'T' here -> skipped safely.
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    pf = PopulationFrequency(
        chrom="chr2", pos=32, ref="A", alt="G", overall_af=0.2, populations={"afr": 0.2}
    )
    assert enumerate_population_sites(SPACER, NRG, reference=ref, variants=[pf], maf=0.001) == []


def test_patient_sites_tagged_patient(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    var = Variant(chrom="chr2", pos=32, ref="T", alt="G")
    sites = enumerate_patient_sites(SPACER, NRG, reference=ref, variants=[var])
    assert len(sites) == 1
    _, prov = sites[0]
    assert prov.origin is SiteOrigin.PATIENT
    assert prov.frequency is None
