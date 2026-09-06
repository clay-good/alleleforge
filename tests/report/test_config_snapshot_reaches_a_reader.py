"""Every setting recorded in provenance must reach a reader somewhere.

The report footer is a curated summary, and `PROVENANCE_FOOTER_OMITTED` is the list of
provenance fields it deliberately skips, each with a reason -- the mechanism that forces
"every omission must be a decision". It had one entry, `config_snapshot`, excused as
"rendered inline beside the results".

The snapshot holds eight keys. Two of them (`intent`, `weights`) are rendered inline.
Three reached no reader at all, and the footer was skipping all eight on the strength of
the two. Each route in `CONFIG_SNAPSHOT_ROUTES` was verified by varying the setting and
reading the rendered page; this file is what keeps them verified.

The trap this file is written around: a page *differing* when a setting changes proves
nothing, because the results differ too. Two of the first checks passed on a diff that
was only the footer timestamp, and a check for the cell-line name passed against a page
that never used it -- "K562" appears in a model card's failure-modes text whatever the
run did. So each check below asserts the specific statement a reader would act on.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.design.ranking import RankingWeights
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.report.builder import CONFIG_SNAPSHOT_ROUTES, build_report
from alleleforge.report.html import render_html
from alleleforge.types.candidate import RankedMenu
from alleleforge.types.edit import EditIntent

VARIANT = "chr2:71:A>C"


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    fasta = tmp_path / "one.fa"
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    return ReferenceGenome(fasta, build="hg38")


def _menu(reference: ReferenceGenome, **kwargs: object) -> RankedMenu:
    kwargs.setdefault("intent", EditIntent.CORRECT)
    return design(VARIANT, reference=reference, **kwargs)  # type: ignore[arg-type]


def _page(reference: ReferenceGenome, **kwargs: object) -> str:
    return render_html(build_report(_menu(reference, **kwargs)))


def test_every_snapshot_key_has_a_documented_route(reference: ReferenceGenome) -> None:
    """A new key must be given a route rather than silently joining the omission."""
    snapshot = _menu(reference).provenance.config_snapshot
    assert snapshot, "no snapshot captured -- this check would be vacuous"
    undocumented = sorted(set(snapshot) - set(CONFIG_SNAPSHOT_ROUTES))
    assert not undocumented, (
        f"config_snapshot keys with no route to a reader: {undocumented}. Render the "
        "key where it takes effect and record how in CONFIG_SNAPSHOT_ROUTES."
    )


def test_documented_routes_are_real_keys(reference: ReferenceGenome) -> None:
    """Guard the guard: a route must not outlive the setting it describes."""
    snapshot = _menu(reference).provenance.config_snapshot
    stale = sorted(set(CONFIG_SNAPSHOT_ROUTES) - set(snapshot))
    assert not stale, f"CONFIG_SNAPSHOT_ROUTES describes keys that no longer exist: {stale}"


def test_intent_is_named(reference: ReferenceGenome) -> None:
    assert "intent knock_out" in _page(reference, intent=EditIntent.KNOCK_OUT)
    assert "intent correct" in _page(reference, intent=EditIntent.CORRECT)


def test_the_ranking_weights_are_named(reference: ReferenceGenome) -> None:
    """Not just "some weights": the values the ranking actually used."""
    page = _page(reference, weights=RankingWeights(efficiency=0.9, cleanliness=0.05, safety=0.05))
    assert "ranking weights: efficiency 0.86" in page, (
        "the summary line must carry the normalized weights the ranking sorted on"
    )
    assert "ranking weights: efficiency 0.35" in _page(reference)  # the default


def test_an_unsearched_offtarget_axis_is_flagged(reference: ReferenceGenome) -> None:
    menu = _menu(reference, run_offtarget=False)
    assert "offtarget-not-searched" in menu.candidates[0].flags
    assert "offtarget-not-searched" in _page(reference, run_offtarget=False)


def test_the_search_extent_is_stated(reference: ReferenceGenome) -> None:
    """`offtarget_regions` reaches the reader as the extent actually covered."""
    assert "off-target search: over " in _page(reference)


def test_unbacked_ancestries_are_named(reference: ReferenceGenome) -> None:
    page = _page(reference, populations=["afr", "eas", "sas"])
    assert "requested but not examined" in page
    for population in ("afr", "eas", "sas"):
        assert population in page


def test_an_unrecognized_cell_context_is_flagged(reference: ReferenceGenome) -> None:
    """`cell_context` reaches a reader only through the distribution check.

    Asserted as a *difference* between two contexts, not as the presence of a name:
    "K562" and "HEK293T" both appear in a model card's failure-modes text on every
    page, whatever the run actually used.
    """
    assert "ood" in _menu(reference, cell_context="not-a-real-cell-line").candidates[0].flags
    assert "ood" not in _menu(reference, cell_context="K562").candidates[0].flags


def test_a_chromatin_track_without_tracks_is_refused(reference: ReferenceGenome) -> None:
    with pytest.raises(ValueError, match="encode_tracks"):
        _menu(reference, chromatin_track="DNase")


def test_the_resolved_settings_reach_the_page(reference: ReferenceGenome) -> None:
    """seed and reference build in the footer; interval_level on every prediction."""
    menu = _menu(reference)
    settings = menu.provenance.config_snapshot["settings"]
    page = render_html(build_report(menu))
    assert f"seed {settings['seed']}" in page
    assert f"reference build {settings['reference']}" in page
    assert f"{settings['interval_level']:.0%} interval" in page
