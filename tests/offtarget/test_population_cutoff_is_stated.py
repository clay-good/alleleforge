"""The MAF cut-off decides which population alleles enter the scan; say so.

`search_description()` names the reporting cut-offs because every number the report
carries is conditional on them. The minimum allele frequency is the same kind of
setting one step earlier -- it decides which population variants are considered at all
-- and it was not named. Against a source holding one 2% PAM-creating variant:

    maf=0.001 -> 1 site,  specificity 0.500
    maf=0.05  -> 0 sites, specificity 1.000

Both descriptions were identical on this axis, and the second is the reassuring one. The
existing note for an inert source made it worse by naming the wrong cause: "supplied but
contributing nothing *in this region*" attributed to the locus what the caller's own
threshold had done.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.data.gnomad import GnomadDB, PopulationFrequency
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM

from .conftest import PAD, SPACER

NRG = PAM(pattern="NRG")


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + PAD + SPACER + "CGT" + PAD + "\n")
    return ReferenceGenome(fasta, build="hg38")


@pytest.fixture
def two_percent_variant() -> GnomadDB:
    """One PAM-creating variant at 2%: a site below MAF 0.05 and above MAF 0.001."""
    return GnomadDB(
        [
            PopulationFrequency(
                chrom="chr2",
                pos=32,
                ref="T",
                alt="G",
                overall_af=0.02,
                populations={"afr": 0.02},
            )
        ]
    )


def test_the_premise_the_cutoff_decides_the_verdict(
    reference: ReferenceGenome, two_percent_variant: GnomadDB
) -> None:
    kwargs = {"reference": reference, "gnomad": two_percent_variant, "populations": ["afr"]}
    loose = search(SPACER, NRG, maf=0.001, **kwargs)
    strict = search(SPACER, NRG, maf=0.05, **kwargs)
    assert loose.n_sites == 1
    assert strict.n_sites == 0
    assert strict.specificity_score() > loose.specificity_score()


def test_the_cutoff_is_named_whenever_it_applied(
    reference: ReferenceGenome, two_percent_variant: GnomadDB
) -> None:
    for maf in (0.001, 0.05):
        description = search(
            SPACER,
            NRG,
            reference=reference,
            gnomad=two_percent_variant,
            populations=["afr"],
            maf=maf,
        ).search_description()
        assert f"population alleles at MAF >= {maf:g}" in description, description


def test_two_cutoffs_do_not_share_one_description(
    reference: ReferenceGenome, two_percent_variant: GnomadDB
) -> None:
    kwargs = {"reference": reference, "gnomad": two_percent_variant, "populations": ["afr"]}
    loose = search(SPACER, NRG, maf=0.001, **kwargs).search_description()
    strict = search(SPACER, NRG, maf=0.05, **kwargs).search_description()
    assert loose != strict


def test_an_inert_source_names_the_cutoff_alongside_the_region(
    reference: ReferenceGenome, two_percent_variant: GnomadDB
) -> None:
    """The note used to blame the locus for what the threshold did."""
    description = search(
        SPACER,
        NRG,
        reference=reference,
        gnomad=two_percent_variant,
        populations=["afr"],
        maf=0.05,
    ).search_description()
    assert "contributing nothing in this region at MAF >= 0.05" in description


def test_a_reference_only_scan_states_no_cutoff(reference: ReferenceGenome) -> None:
    """Guard the guard: with no ancestry source the cut-off never applied.

    Printing it would describe a filter that did nothing, and a provenance line that is
    always present teaches a reader to skip provenance lines.
    """
    report = search(SPACER, NRG, reference=reference)
    assert report.maf_threshold is None
    assert "MAF" not in report.search_description()
