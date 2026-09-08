"""The ancestry stratification reported three identical numbers on the finding it exists for.

`ancestry_stratification()` returns the worst-case *score* per ancestry, and a CFD score
does not depend on ancestry — only on the sequence. So on the reference-bias reproduction
this engine was built for (a minor allele creating a de-novo PAM, enriched in African
ancestry), the CLI printed:

    worst off-target score by ancestry: afr 1.000, amr 1.000, nfe 1.000

Three identical numbers over carrying frequencies of 0.105, 0.012 and 0.001. A reader takes
that as risk spread evenly across populations — the opposite of the published finding, and
the opposite of what the site line beneath it says.

The blindness was already named one method up. `expected_burden`'s docstring says it
"separates a rare-variant off-target from a universal one, which the frequency-blind
`worst_score` and `specificity_score` cannot" — and the ancestry axis, the single thing the
population-aware search is *for*, was reported with the frequency-blind statistic.

Added, not substituted: "is there a dangerous site at all" and "how often is it actually
there" are two questions, and `worst_ancestry` still drives the ranking safety axis
untouched. Only the second question had no answer.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from alleleforge.data.gnomad import GnomadDB, PopulationFrequency
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM

from .conftest import PAD, SPACER

MakeRef = Callable[[dict[str, str]], ReferenceGenome]
NGG = PAM(pattern="NGG")

#: The rs114518452-like allele from `test_reference_bias.py`: AFR-enriched, rare elsewhere.
_ALLELE = PopulationFrequency(
    chrom="chr2",
    pos=32,
    ref="T",
    alt="G",
    overall_af=0.03,
    populations={"afr": 0.105, "amr": 0.012, "eas": 0.0, "nfe": 0.001, "sas": 0.0},
)


@pytest.fixture
def report(make_reference: MakeRef) -> object:
    reference = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    return search(SPACER, NGG, reference=reference, gnomad=GnomadDB([_ALLELE]))


def test_the_worst_score_really_is_flat_across_ancestries(report: object) -> None:
    """The premise. Without it the rest of this file passes for the wrong reason."""
    strata = report.ancestry_stratification()  # type: ignore[attr-defined]
    assert len(strata) > 1, strata
    assert len(set(strata.values())) == 1, (
        f"the fixture no longer exhibits the condition: {strata}. This file is about a "
        "stratification that cannot distinguish ancestries; pick an allele where it "
        "cannot."
    )


def test_the_burden_separates_what_the_score_cannot(report: object) -> None:
    burden = report.ancestry_expected_burden()  # type: ignore[attr-defined]
    assert set(burden) == set(report.ancestry_stratification()), burden  # type: ignore[attr-defined]
    # The published finding: concentrated in African ancestry, near-absent in Europeans.
    assert burden["afr"] > burden["amr"] > burden["nfe"], burden
    assert burden["afr"] == pytest.approx(0.105, abs=1e-6), burden
    assert burden["nfe"] == pytest.approx(0.001, abs=1e-6), burden


def test_an_unattributed_site_counts_for_every_ancestry() -> None:
    """A reference site is in every genome, so it must not be discounted anywhere.

    The same rule `ancestry_stratification` and `expected_burden` follow: not knowing
    which stratum carries a site is not a reason to weight it down.

    Built from sites directly rather than from a scan. The engine will not produce a
    report holding both an unattributed site *and* an ancestry-annotated one over a
    fixture this small — the first draft of this test used a contig where the reference
    already carried the PAM, which leaves no population site, no annotated ancestries,
    and an empty mapping the assertions then ranged over vacuously. The method is a pure
    function of `sites`, so the honest fixture is the pair of sites.
    """
    from alleleforge.types.offtarget import (
        OffTargetReport,
        OffTargetSite,
        ScoreMethod,
        SiteOrigin,
    )
    from alleleforge.types.sequence import GenomicInterval

    reference_site = OffTargetSite(
        locus=GenomicInterval.parse("chr2:10-30"),
        mismatches=0,
        score=0.8,
        score_method=ScoreMethod.CFD,
    )
    population_site = OffTargetSite(
        locus=GenomicInterval.parse("chr2:50-70"),
        mismatches=1,
        score=1.0,
        score_method=ScoreMethod.CFD,
        origin=SiteOrigin.POPULATION,
        causal_allele="chr2:55:T>G",
        populations=("afr",),
        frequency=0.105,
        ancestries={"afr": 0.105, "nfe": 0.001},
    )
    report = OffTargetReport(spacer=SPACER, pam="NGG", sites=(reference_site, population_site))

    burden = report.ancestry_expected_burden()
    assert set(burden) == {"afr", "nfe"}, burden
    # 0.8 at full weight everywhere, plus the population site at its own frequency.
    assert burden["afr"] == pytest.approx(0.8 + 1.0 * 0.105), burden
    assert burden["nfe"] == pytest.approx(0.8 + 1.0 * 0.001), burden
    # And the reference site alone would still leave every stratum above its own score.
    assert min(burden.values()) > reference_site.score


def test_a_reference_only_scan_has_no_ancestry_burden(make_reference: MakeRef) -> None:
    """No annotated ancestry, no strata — not a row of zeroes implying it was measured."""
    reference = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    assert search(SPACER, NGG, reference=reference).ancestry_expected_burden() == {}


@pytest.mark.parametrize("surface", ["cli-human", "cli-json"])
def test_the_number_reaches_the_surfaces_that_show_the_score(
    surface: str, make_reference: MakeRef, tmp_path: object
) -> None:
    """The score has been on these since it existed; the frequency has not."""
    import json
    from pathlib import Path

    from typer.testing import CliRunner

    from alleleforge.cli.main import app

    directory = Path(str(tmp_path))
    fasta = directory / "chr2.fa"
    fasta.write_text(">chr2\n" + PAD + SPACER + "CGT" + PAD + "\n")
    sites = directory / "gnomad.tsv"
    sites.write_text(
        "#chrom\tpos\tref\talt\taf\tafr\tamr\teas\tnfe\tsas\n"
        "chr2\t33\tT\tG\t0.03\t0.105\t0.012\t0.0\t0.001\t0.0\n"
    )
    argv = [
        "offtarget",
        SPACER,
        "--reference-fasta",
        str(fasta),
        "--gnomad",
        str(sites),
        "--populations",
        "afr,amr,nfe",
    ]
    if surface == "cli-json":
        argv.append("--json")
    result = CliRunner().invoke(app, argv)
    assert result.exit_code == 0, result.output + result.stderr

    if surface == "cli-json":
        payload = json.loads(result.stdout)
        assert (
            payload["ancestry_expected_burden"]["afr"]
            > (payload["ancestry_expected_burden"]["nfe"])
        ), payload["ancestry_expected_burden"]
    else:
        assert "expected burden by ancestry" in result.output, result.output
        assert "afr 0.1050" in result.output, result.output
