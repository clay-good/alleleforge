"""A guide with a plausible cut elsewhere in the genome must say so.

The number was always there — a report prints `off-target sites: 2 (specificity
0.376)` — but the CAVEATS block, which is what a reader scans for *what should worry
me*, listed spacer GC and bystander bases and said nothing about a site scoring 1.000.
The three verticals flagged off-targets three different ways: cas9 and the base editor
emitted `population-offtarget`, prime did not (its flag builder was never passed the
report at all), and none of them flagged a high-scoring site.

The ranking did consume it — the safety objective drops toward 0 — so such a guide
sinks in a full menu. It is still returned `recommended` when it is the only
candidate, which is exactly when the caveat matters most.
"""

from __future__ import annotations

import pytest

from alleleforge.design.offtarget_flags import HIGH_SCORE_BAND, offtarget_flags
from alleleforge.types.offtarget import OffTargetReport, OffTargetSite, ScoreMethod
from alleleforge.types.sequence import GenomicInterval, Strand

SPACER = "GACCCCCTCCACCCCGCCTC"


def _report(*scores: float, origin: str = "reference") -> OffTargetReport:
    sites = tuple(
        OffTargetSite(
            locus=GenomicInterval(
                chrom="chr1", start=100 + i * 30, end=120 + i * 30, strand=Strand.PLUS
            ),
            mismatches=2,
            score=score,
            score_method=ScoreMethod.CFD,
            origin=origin,  # type: ignore[arg-type]
        )
        for i, score in enumerate(scores)
    )
    return OffTargetReport(
        spacer=SPACER,
        pam="NGG",
        sites=sites,
        mismatch_threshold=4,
        dna_bulge_budget=1,
        rna_bulge_budget=1,
        cfd_threshold=0.2,
        mit_threshold=0.1,
        searched_bases=1000,
        resolved_bases=1000,
        reference_build="hg38",
        scorer="CFD",
    )


def test_a_high_scoring_site_raises_a_caveat() -> None:
    flags = offtarget_flags(_report(1.0, 0.21))
    assert any(f.startswith("offtarget-high:") for f in flags), flags
    # The score travels with the flag, so a reader judges rather than trusting a band.
    assert "offtarget-high:1.00" in flags


def test_only_weak_nominations_raise_no_caveat() -> None:
    """Sites below the band are still counted and reported — they just do not alarm."""
    flags = offtarget_flags(_report(0.21, 0.3))
    assert not any(f.startswith("offtarget-high:") for f in flags), flags


def test_the_band_is_the_boundary() -> None:
    assert any(f.startswith("offtarget-high") for f in offtarget_flags(_report(HIGH_SCORE_BAND)))
    assert not any(
        f.startswith("offtarget-high") for f in offtarget_flags(_report(HIGH_SCORE_BAND - 0.01))
    )


def test_an_unsearched_candidate_says_so_and_nothing_else() -> None:
    """ "Not searched" must not be confused with "searched and clean"."""
    assert offtarget_flags(None) == ["offtarget-not-searched"]


def test_the_high_score_caveat_is_classified() -> None:
    """A hazard flag with no reason behind it never reaches the caveats block."""
    from alleleforge.report.builder import caveats

    found = dict(caveats(("offtarget-high:1.00",)))
    assert found, "the flag produced no caveat"
    assert "elsewhere in the genome" in next(iter(found.values()))


@pytest.mark.parametrize("vertical", ["cas9", "prime", "base_editor"])
def test_every_vertical_uses_the_shared_helper(vertical: str) -> None:
    """The three had drifted; prime never even received the report to flag from."""
    import inspect

    from alleleforge.design import base_editor, cas9, prime

    module = {"cas9": cas9, "prime": prime, "base_editor": base_editor}[vertical]
    source = inspect.getsource(module)
    assert "offtarget_flags(" in source, f"{vertical} does not use the shared helper"
    # ...and no vertical keeps a hand-rolled copy of what the helper now owns.
    assert 'flags.append("population-offtarget")' not in source
    assert 'flags.append("offtarget-not-searched")' not in source
