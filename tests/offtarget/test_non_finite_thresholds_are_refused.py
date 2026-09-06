"""A NaN fraction must be refused, not silently reinterpreted.

`--cfd-threshold -1`, `2` and `inf` are all rejected with a usage error. `nan` was
accepted, because Click's `min=0.0, max=1.0` is a pair of comparisons and every
comparison against NaN is False. The value then reached a consumer that compared
against it, where the same property decided the outcome by the direction the consumer's
test happened to be written in:

* the site filter is a *skip* test, so a NaN threshold skipped nothing and reported
  every site -- while the report printed ``sites reported at CFD >= nan``;
* the population filter is an *include* test, so a NaN ``maf`` admitted nothing and
  every population off-target vanished, leaving a clean bill of health on the
  population-safety axis with no error and no warning.

This is the class of defect this project keeps rediscovering: a real safety input inert
on the axis it governs, with a green suite. These pin the refusal at the two public
entry points that take these fractions, and that the refusal names the offender.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path

import pytest

from alleleforge.data.gnomad import PopulationFrequency
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.offtarget.population import enumerate_population_sites
from alleleforge.types.guide import PAM

from .conftest import PAD, SPACER

NRG = PAM(pattern="NRG")
NGG = PAM(pattern="NGG")
MakeRef = Callable[[dict[str, str]], ReferenceGenome]

#: Values Click's range check lets through unchanged. `inf` is orderable, so it is
#: caught by `max=1.0` at the shell -- but nothing stops a library or web caller
#: passing it, and it silently means "report nothing" rather than any cutoff.
NON_FINITE = [float("nan"), float("inf"), float("-inf")]


@pytest.fixture
def population_reference(make_reference: MakeRef) -> ReferenceGenome:
    """A contig where one common variant creates a perfect-match PAM."""
    return make_reference({"chr2": PAD + SPACER + "CGT" + PAD})


@pytest.fixture
def common_variant() -> PopulationFrequency:
    """A T->G at the PAM's third base, at 10% in `afr` -- well above any real `maf`."""
    return PopulationFrequency(
        chrom="chr2",
        pos=32,
        ref="T",
        alt="G",
        overall_af=0.05,
        populations={"afr": 0.10, "nfe": 0.01},
    )


def test_a_real_maf_finds_the_population_site(
    population_reference: ReferenceGenome, common_variant: PopulationFrequency
) -> None:
    """The premise: with a sane `maf` this variant really is reported."""
    sites = enumerate_population_sites(
        SPACER, NRG, reference=population_reference, variants=[common_variant], maf=0.001
    )
    assert len(sites) == 1, "the fixture must produce a site, or the NaN case proves nothing"


@pytest.mark.parametrize("maf", NON_FINITE, ids=repr)
def test_population_search_refuses_a_non_finite_maf(
    maf: float, population_reference: ReferenceGenome, common_variant: PopulationFrequency
) -> None:
    with pytest.raises(ValueError, match="finite"):
        enumerate_population_sites(
            SPACER, NRG, reference=population_reference, variants=[common_variant], maf=maf
        )


@pytest.mark.parametrize("name", ["maf", "cfd_threshold", "mit_threshold"])
@pytest.mark.parametrize("value", NON_FINITE, ids=repr)
def test_search_refuses_every_non_finite_fraction(
    name: str, value: float, population_reference: ReferenceGenome
) -> None:
    with pytest.raises(ValueError, match=r"finite fraction") as excinfo:
        search(SPACER, NGG, reference=population_reference, **{name: value})
    # Naming the offending parameter is the point: a caller passing three fractions
    # cannot act on "a threshold must be finite".
    assert name in str(excinfo.value)


def test_the_cli_rejects_a_non_finite_threshold(
    population_reference: ReferenceGenome, tmp_path: Path
) -> None:
    """The shell surface, where `-1`, `2` and `inf` were already refused and `nan` was not."""
    from typer.testing import CliRunner

    from alleleforge.cli.main import app

    result = CliRunner().invoke(
        app,
        [
            "offtarget",
            SPACER,
            "--reference-fasta",
            str(population_reference.path),
            "--cfd-threshold",
            "nan",
            "--dna-bulges",
            "0",
            "--rna-bulges",
            "0",
        ],
    )
    assert result.exit_code != 0, f"nan was accepted: {result.output}"


def test_finite_fractions_still_pass() -> None:
    """Guard the guard: the check must not reject the values it exists to protect."""
    from alleleforge.offtarget._bounds import reject_non_finite

    reject_non_finite(maf=0.0, cfd_threshold=0.2, mit_threshold=1.0)
    assert math.isfinite(0.0)  # the boundary values are finite; nothing was raised
