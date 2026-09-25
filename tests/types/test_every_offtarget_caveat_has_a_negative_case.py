"""Every off-target caveat must stay silent when its condition does not hold.

Mutation testing over `types/offtarget.py` killed 52 of 60 mutants and left 8 alive.
All 8 sat in the caveat machinery — the clauses that decide what a reader is told about
a scan. Each survivor is a predicate whose *negative* case nothing asserted: flip
`is not` to `is`, `!=` to `==`, `>` to `>=`, and 484 focused tests still pass.

The arithmetic was right in every case; this file is the measurement it never had. What
was missing is the half of each claim that says the sentence stays away when it does not
apply — and a caveat that fires when it should not is worse than one that never fires,
because it spends a reader's attention on a false alarm they cannot act on. Two of these
tell a caller their population file is for the wrong assembly.

The sharpest one: `population_sites` filters `origin is not REFERENCE`, and its only test
built one reference site and one population site and asserted the count was 1 — true
whichever side the filter selects. A symmetric fixture measured by a count cannot say
which half came back. It feeds the `population-offtarget` flag, so inverted it would
announce population risk on a reference-only report and stay silent on a population-driven
one, in the feature this project is built around.
"""

from __future__ import annotations

from alleleforge.design.offtarget_flags import offtarget_flags
from alleleforge.types.offtarget import (
    OffTargetReport,
    OffTargetSite,
    ScoreMethod,
    SiteOrigin,
    build_mismatch_note,
    headline_notes,
)
from alleleforge.types.sequence import GenomicInterval, Strand


def _locus(start: int = 0, end: int = 20) -> GenomicInterval:
    return GenomicInterval(chrom="chr2", start=start, end=end, strand=Strand.PLUS)


def _ref_site(score: float = 0.3) -> OffTargetSite:
    return OffTargetSite(locus=_locus(), mismatches=2, score=score, score_method=ScoreMethod.CFD)


def _pop_site(score: float = 0.9, ancestry: str = "afr", freq: float = 0.02) -> OffTargetSite:
    return OffTargetSite(
        locus=_locus(50, 70),
        mismatches=1,
        score=score,
        score_method=ScoreMethod.CFD,
        origin=SiteOrigin.POPULATION,
        causal_allele="chr2:55:A>G",
        populations=(ancestry,),
        frequency=freq,
        ancestries={ancestry: freq},
    )


def _report(**kwargs: object) -> OffTargetReport:
    base: dict[str, object] = {"spacer": "A" * 20, "pam": "NGG", "searched_bases": 1000}
    base.update(kwargs)
    return OffTargetReport(**base)  # type: ignore[arg-type]


# -- which sites are "population" sites ---------------------------------------


def test_population_sites_selects_the_population_site_not_the_reference_one() -> None:
    """Identity, not count: the fixture is asymmetric so the two cannot be confused.

    The pre-existing check built one site of each kind and asserted `len(...) == 1`,
    which holds whichever side `origin is not REFERENCE` selects.
    """
    ref, pop = _ref_site(), _pop_site()
    report = _report(sites=(ref, pop))
    assert report.population_sites == (pop,), (
        "population_sites must return the population site itself, not merely one site"
    )


def test_a_reference_only_report_raises_no_population_flag() -> None:
    """The negative case of the flag `population_sites` exists to raise."""
    assert "population-offtarget" not in offtarget_flags(_report(sites=(_ref_site(),)))
    assert "population-offtarget" in offtarget_flags(_report(sites=(_pop_site(),)))


def test_two_population_sites_are_both_selected() -> None:
    """A count of 1 is also blind to a filter that stops after the first match."""
    a, b = _pop_site(0.9), _pop_site(0.4, "eas", 0.05)
    assert _report(sites=(_ref_site(), a, b)).population_sites == (a, b)


# -- the PAM-broadening disclosure --------------------------------------------


def test_the_pam_broadening_note_is_absent_when_the_pam_was_not_broadened() -> None:
    """`scanned_pam != pam` is the whole claim, so both sides need stating.

    Inverted, the sentence appears on exactly the scans that did *not* broaden — and a
    reader told that low-stringency sites were nominated will read the site list as
    more complete than it is.
    """
    widened = _report(sites=(_ref_site(),), scanned_pam="NRG").search_description()
    assert "the PAM was broadened from NGG to NRG" in widened

    same = _report(sites=(_ref_site(),), scanned_pam="NGG").search_description()
    assert "broadened" not in same, "a scan at the configured PAM must not claim broadening"

    unset = _report(sites=(_ref_site(),)).search_description()
    assert "broadened" not in unset


# -- "your file is for the wrong build" ---------------------------------------


def test_a_source_with_no_build_mismatch_is_not_reported_as_mismatched() -> None:
    """A zero count is the ordinary case and must produce no sentence.

    `n > 0` filters the tally. Relaxed to `n >= 0`, every supplied source is named as
    carrying records for another assembly — a false alarm, on the one clause in this
    paragraph that has a remedy, telling a caller to go and replace a file that is fine.
    """
    clean = _report(
        sites=(_ref_site(),), sources_considered={"gnomad": 5}, source_build_mismatch={"gnomad": 0}
    )
    assert "that is a build mismatch" not in clean.search_description()
    assert "gnomad record(s)" not in clean.search_description()
    assert build_mismatch_note(clean) is None

    dirty = _report(
        sites=(_ref_site(),), sources_considered={"gnomad": 5}, source_build_mismatch={"gnomad": 2}
    )
    assert "that is a build mismatch" in dirty.search_description()
    assert build_mismatch_note(dirty) is not None


def test_a_wholesale_build_mismatch_reads_differently_from_one_stale_record() -> None:
    """`count >= total` picks the wording, and the two say different things.

    The code's own comment is the specification: "every one of the 2" is a file for the
    wrong build, "1 of the 2" is one stale record in a good file. At `count == total`
    the strict `>` renders the reassuring half of that pair for the worst case.
    """
    whole = _report(
        sites=(_ref_site(),), sources_considered={"gnomad": 2}, source_build_mismatch={"gnomad": 2}
    ).search_description()
    assert "every one of the 2 gnomad record(s)" in whole

    partial = _report(
        sites=(_ref_site(),), sources_considered={"gnomad": 2}, source_build_mismatch={"gnomad": 1}
    ).search_description()
    assert "1 of the 2 gnomad record(s)" in partial
    assert "every one of" not in partial


def test_the_two_build_mismatch_renderings_agree_on_when_to_speak() -> None:
    """One rule, two implementations: the paragraph's clause and the headline note.

    `search_description` filters `n > 0` and `build_mismatch_note` filters `if count`.
    They must agree, or a headline warns about a file the paragraph calls clean.
    """
    for tally in ({}, {"gnomad": 0}, {"gnomad": 1}, {"gnomad": 0, "haplotypes": 3}):
        report = _report(
            sites=(_ref_site(),),
            sources_considered={"gnomad": 4, "haplotypes": 4},
            source_build_mismatch=tally,
        )
        # The two surfaces word it differently on purpose — the paragraph explains, the
        # headline is bracket-ready — so each is probed by its own sentence.
        in_paragraph = "that is a build mismatch" in report.search_description()
        assert (build_mismatch_note(report) is not None) is in_paragraph, (
            f"the headline note and the paragraph disagree for {tally}"
        )


# -- cut-offs that are reachable ----------------------------------------------


def test_a_cutoff_of_exactly_one_is_not_called_unreachable() -> None:
    """1.0 is a reachable CFD/MIT score — a perfect match scores it.

    `value > 1.0` is the test for "no site can clear this". Relaxed to `>= 1.0`, a
    caller who deliberately asked for perfect matches only is told their empty site
    list is an artifact of an impossible cut-off, which inverts what the 0 means.
    """
    strict = _report(sites=(), cfd_threshold=1.0, mit_threshold=1.0)
    assert not any("no site can clear" in n for n in headline_notes(strict))

    impossible = _report(sites=(), cfd_threshold=1.5, mit_threshold=1.5)
    assert any("no site can clear" in n for n in headline_notes(impossible))


def test_a_maf_of_exactly_one_is_not_called_unreachable() -> None:
    """MAF 1.0 selects alleles fixed in the population, which exist."""
    fixed = _report(sites=(_ref_site(),), maf_threshold=1.0)
    assert not any("no allele can reach" in n for n in headline_notes(fixed))

    impossible = _report(sites=(_ref_site(),), maf_threshold=1.5)
    assert any("no allele can reach" in n for n in headline_notes(impossible))


# -- how much of the requested extent was searchable --------------------------


def test_a_searchable_extent_at_the_materiality_threshold_is_not_flagged() -> None:
    """0.99 is a deliberate materiality line, so the boundary itself needs pinning.

    "A genome with a few scattered ambiguity codes is not news, a region that is half gap
    is." `fraction < 0.99` draws that line; relaxed to `<=`, a 99%-resolved scan starts
    carrying a coverage warning, which is the noise the threshold exists to suppress.
    This mutant is the one that survived a 484-test sweep as well as a focused one.
    """
    at_line = _report(sites=(_ref_site(),), searched_bases=1000, resolved_bases=990)
    assert "were searchable" not in at_line.search_description()

    below = _report(sites=(_ref_site(),), searched_bases=1000, resolved_bases=989)
    assert "only 99% of the 1,000 requested bases were searchable" in below.search_description()


def test_the_searchable_fraction_is_resolved_over_searched() -> None:
    """The ratio's direction and operands, on numbers where no other arithmetic agrees.

    With the default `resolved_bases` of 0 the quotient and the product are both 0, so a
    fixture that leaves it unset cannot tell a division from a multiplication.
    """
    report = _report(sites=(_ref_site(),), searched_bases=1000, resolved_bases=500)
    assert "only 50% of the 1,000 requested bases were searchable" in report.search_description()


def test_a_guide_length_query_carries_no_length_caveat() -> None:
    """The caveat that a query is not a guide, in both directions.

    Inverted, every ordinary 20-nt spacer is announced as "not a guide length — this is a
    sequence search, not an off-target profile", which disclaims the entire report.
    """
    ordinary = _report(sites=(), spacer="A" * 20)
    assert not any("not a guide length" in n for n in headline_notes(ordinary))

    too_long = _report(sites=(), spacer="A" * 40)
    assert any("not a guide length" in n for n in headline_notes(too_long))


# -- "nothing was searched" ---------------------------------------------------


def test_the_empty_search_note_is_absent_when_bases_were_searched() -> None:
    """The note that a result is empty rather than clean, in both directions.

    This is the most consequential sentence the report can carry, and inverted it
    attaches to every scan that *did* search — so the one reassurance a reader can act
    on ("nothing was found") starts arriving with a warning that nothing was looked at.
    """
    searched = _report(sites=(), searched_bases=1000)
    assert not any("NO SEQUENCE WAS SEARCHED" in n for n in headline_notes(searched))

    empty = _report(sites=(), searched_bases=0)
    assert any("NO SEQUENCE WAS SEARCHED" in n for n in headline_notes(empty))


def test_the_empty_search_note_agrees_with_the_paragraph() -> None:
    """The same claim is made in `search_description` and in `headline_notes`."""
    for bases in (0, 1000):
        report = _report(sites=(), searched_bases=bases)
        in_notes = any("NO SEQUENCE WAS SEARCHED" in n for n in headline_notes(report))
        in_paragraph = "NO SEQUENCE WAS SEARCHED" in report.search_description()
        assert in_notes is in_paragraph, f"the two surfaces disagree at searched_bases={bases}"
