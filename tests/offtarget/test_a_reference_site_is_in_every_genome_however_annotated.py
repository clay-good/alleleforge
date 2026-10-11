"""A reference off-target is present in every genome, whatever frequency it carries.

Four places in the off-target report ask the same two-part question — is this site in the
reference, *or* does it lack a frequency — and treat either answer as "weight it 1.0, and
do not attribute it to an ancestry". Every population fixture in the suite is a
non-reference site that has a frequency, and every reference fixture has none, so the two
arms of that guard always agreed and dropping either one was invisible: a conjunct-removal
sweep left one arm of each unkilled.

The fixture that separates them is a **reference site that carries a frequency**, which is
constructible and meaningful — a reference-genome hit can be annotated from a population
database without ceasing to be in every genome. If the origin arm were dropped, such a
site would be weighted by its frequency instead of by 1.0: a 0.001-frequency annotation
turns a score of 0.9 into a burden of 0.0009, understating by a thousandfold a hit that
every patient actually has. That is the direction this project has twice found safety
numbers failing in, so it gets a fixture rather than an argument.
"""

from __future__ import annotations

import pytest

from alleleforge.types.offtarget import (
    OffTargetReport,
    OffTargetSite,
    ScoreMethod,
    SiteOrigin,
)
from alleleforge.types.sequence import GenomicInterval, Strand

_LOCUS = GenomicInterval(chrom="chr1", start=10, end=30, strand=Strand.PLUS)


def _site(**kw: object) -> OffTargetSite:
    base: dict[str, object] = {
        "locus": _LOCUS,
        "mismatches": 2,
        "score": 0.9,
        "score_method": ScoreMethod.CFD,
    }
    base.update(kw)
    return OffTargetSite(**base)  # type: ignore[arg-type]


def _report(*sites: OffTargetSite) -> OffTargetReport:
    return OffTargetReport(
        spacer="A" * 20,
        pam="NGG",
        searched_bases=1_000,
        resolved_bases=1_000,
        sites=sites,
    )


def _population(**kw: object) -> OffTargetSite:
    """A population site, which the model requires to name the allele that creates it."""
    return _site(
        origin=SiteOrigin.POPULATION,
        causal_allele="chr1:15:A>G",
        **kw,  # type: ignore[arg-type]
    )


#: The fixture the whole file exists for: in the reference *and* frequency-annotated.
def _annotated_reference_site() -> OffTargetSite:
    return _site(
        origin=SiteOrigin.REFERENCE,
        frequency=0.001,
        ancestries={"afr": 0.002},
    )


def test_the_fixture_really_holds_both_properties_at_once() -> None:
    """Assert the premise: without both, every assertion below is vacuous."""
    site = _annotated_reference_site()
    assert site.origin is SiteOrigin.REFERENCE
    assert site.frequency is not None
    assert site.ancestries


def test_an_annotated_reference_site_is_weighted_one_not_by_its_frequency() -> None:
    report = _report(_annotated_reference_site())
    assert report.expected_burden() == pytest.approx(0.9), (
        "a reference hit is in every genome; weighting it by a 0.001 annotation "
        "understates it a thousandfold"
    )


def test_an_annotated_reference_site_is_not_probabilistic_presence() -> None:
    report = _report(_annotated_reference_site())
    assert report.is_frequency_weighted() is False, (
        "nothing here is probabilistic: the one site is in the reference"
    )


def test_an_annotated_reference_site_is_not_a_population_site() -> None:
    assert _report(_annotated_reference_site()).population_sites == ()


def test_an_annotated_reference_sites_score_reaches_every_ancestry() -> None:
    """Unattributed, so it is the worst case everywhere, not only where it is annotated."""
    report = _report(
        _annotated_reference_site(),
        _population(frequency=0.5, ancestries={"eas": 0.5}, score=0.2),
    )
    strata = report.ancestry_stratification()
    assert set(strata) == {"afr", "eas"}
    assert strata["eas"] == pytest.approx(0.9), (
        "the reference site is unattributed, so it is the worst case for an ancestry "
        "it does not name"
    )
    assert strata["afr"] == pytest.approx(0.9)


def test_an_annotated_reference_site_counts_in_full_in_every_ancestrys_burden() -> None:
    report = _report(_annotated_reference_site())
    burden = report.ancestry_expected_burden()
    assert burden["afr"] == pytest.approx(0.9), "full score, not 0.9 * 0.001"


# --- the negative case: a population site with a frequency IS weighted -------------


def test_a_population_site_with_a_frequency_is_still_weighted_by_it() -> None:
    """Without this, every assertion above would also pass if weighting were removed."""
    report = _report(_population(frequency=0.001))
    assert report.expected_burden() == pytest.approx(0.0009)
    assert report.is_frequency_weighted() is True
    assert len(report.population_sites) == 1


def test_a_population_site_with_no_frequency_is_unattributed_in_every_ancestry() -> None:
    """The third arm of `REFERENCE or frequency is None or not ancestries`.

    A population site can name the ancestries it was seen in and still carry no
    frequency — gnomAD lists the allele without a usable AF. It is then unattributed:
    nothing is known about how often it is carried, so it counts in full everywhere
    rather than being scaled by a frequency that does not exist.

    Every other fixture in this file satisfies two arms of that chain at once (a
    reference site with a frequency, or a population site with one), so the
    `frequency is None` arm decided nothing and could be dropped.
    """
    site = _population(frequency=None, ancestries={"afr": 0.3}, score=0.8)
    assert site.origin is not SiteOrigin.REFERENCE, "arm 1 must not fire"
    assert site.frequency is None, "arm 2 is the one under test"
    assert site.ancestries, "arm 3 must not fire"

    report = _report(site)
    assert report.expected_burden() == pytest.approx(0.8), "no frequency, so no scaling"
    assert report.ancestry_stratification()["afr"] == pytest.approx(0.8)
    assert report.ancestry_expected_burden()["afr"] == pytest.approx(0.8)


def test_a_population_site_with_a_frequency_is_attributed_to_its_own_ancestry_only() -> None:
    """The negative case: with a frequency, the chain must NOT call it unattributed."""
    report = _report(
        _population(frequency=0.4, ancestries={"afr": 0.4}, score=0.8),
        _population(frequency=0.4, ancestries={"eas": 0.4}, score=0.3),
    )
    strata = report.ancestry_stratification()
    assert strata["afr"] == pytest.approx(0.8)
    assert strata["eas"] == pytest.approx(0.3), (
        "an attributed site must not set the worst case for an ancestry it does not name"
    )


def test_a_frequencyless_site_is_charged_to_an_ancestry_it_does_not_name() -> None:
    """Unattributed means charged everywhere, including where it was never seen.

    The previous test could not separate the arms after all: a site whose `ancestries`
    *include* the ancestry being asked about reaches the same answer down either
    branch — unattributed takes it in full, and the attributed branch takes it too
    because its share for that ancestry is positive. The two paths only diverge for an
    ancestry the site does **not** name, which needs a second site to put that
    ancestry in play at all.
    """
    report = _report(
        _population(frequency=None, ancestries={"afr": 0.3}, score=0.8),
        _population(frequency=0.4, ancestries={"eas": 0.4}, score=0.1),
    )
    strata = report.ancestry_stratification()
    assert strata["eas"] == pytest.approx(0.8), (
        "a site with no frequency is of unknown prevalence, so it is the worst case "
        "for every ancestry — not only the ones it happens to name"
    )
    assert report.ancestry_expected_burden()["eas"] == pytest.approx(0.8 + 0.1 * 0.4)


def test_a_site_naming_no_ancestry_at_all_is_charged_everywhere() -> None:
    """The third arm on its own: a frequency, but no ancestry breakdown.

    `not ancestries` is the deciding operand only when the other two do not fire — a
    population site that carries a frequency but no per-ancestry shares, which is what
    a frequency source without a population breakdown gives you.
    """
    site = _population(frequency=0.4, ancestries={}, score=0.7)
    assert site.origin is not SiteOrigin.REFERENCE and site.frequency is not None
    assert not site.ancestries, "the arm under test"

    report = _report(site, _population(frequency=0.2, ancestries={"eas": 0.2}, score=0.1))
    assert report.ancestry_stratification()["eas"] == pytest.approx(0.7), (
        "a site with no ancestry breakdown cannot be excluded from any ancestry"
    )
    assert report.ancestry_expected_burden()["eas"] == pytest.approx(0.7 + 0.1 * 0.2)
