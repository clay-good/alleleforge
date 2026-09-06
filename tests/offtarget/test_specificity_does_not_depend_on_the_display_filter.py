"""Tightening the reporting threshold must not improve the specificity score.

`specificity_score` is `1 / (1 + Σ reported + subthreshold_score_sum)`, and the second
term exists precisely so the cut-off decides what is *shown* and not what is *counted*.
That makes an invariant: the same guide over the same reference reports the same
specificity at every reporting threshold, while the number of displayed sites falls.

If it ever stopped holding, the failure has a direction. Raising `--cfd-threshold` would
drop sites out of `sites` without moving their weight into the tail, and the aggregate
safety number would go *up* — a guide could be made to look more specific by asking to
be shown less. That is the same reassuring-direction defect this project keeps finding,
and it would be available to anyone tuning a flag.

The pieces are unit-tested — the formula includes the tail, merging two nick reports sums
it, the engine produces a non-zero one — and the property they exist to produce was not.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM
from alleleforge.types.offtarget import OffTargetReport

from .conftest import PAD, SPACER

NGG = PAM(pattern="NGG")
#: Spanning the whole range, so the reported set goes from "everything" to "one site".
THRESHOLDS = (0.0, 0.05, 0.2, 0.5, 0.9, 1.0)


@pytest.fixture
def graded_reference(tmp_path: Path) -> ReferenceGenome:
    """A contig carrying the spacer plus four near-matches, so scores span the range."""
    variants = [
        SPACER,
        SPACER[:-1] + "A",
        SPACER[:-2] + "AA",
        "A" + SPACER[1:-1] + "T",
        SPACER[:10] + "A" + SPACER[11:],
    ]
    contig = PAD + ("CGG" + PAD).join(variants) + "CGG" + PAD
    fasta = tmp_path / "graded.fa"
    fasta.write_text(">chr2\n" + contig + "\n")
    return ReferenceGenome(fasta, build="hg38")


def _reports(reference: ReferenceGenome) -> list[OffTargetReport]:
    return [
        search(SPACER, NGG, reference=reference, cfd_threshold=t, mit_threshold=1.1)
        for t in THRESHOLDS
    ]


def test_the_premise_the_threshold_really_changes_what_is_shown(
    graded_reference: ReferenceGenome,
) -> None:
    """A floor: without a spread of displayed counts the invariance proves nothing."""
    counts = [r.n_sites for r in _reports(graded_reference)]
    assert counts[0] > counts[-1], f"the threshold changed nothing: {counts}"
    assert counts[0] >= 4, f"too few sites to be testing a spread: {counts}"
    assert counts[-1] >= 1


def test_specificity_is_identical_at_every_reporting_threshold(
    graded_reference: ReferenceGenome,
) -> None:
    scores = [r.specificity_score() for r in _reports(graded_reference)]
    assert scores == pytest.approx([scores[0]] * len(scores)), dict(
        zip(THRESHOLDS, scores, strict=True)
    )


def test_what_leaves_the_reported_set_arrives_in_the_tail(
    graded_reference: ReferenceGenome,
) -> None:
    """The mechanism behind the invariance, stated directly."""
    totals = [
        sum(s.score for s in r.sites) + r.subthreshold_score_sum for r in _reports(graded_reference)
    ]
    assert totals == pytest.approx([totals[0]] * len(totals))


def test_tightening_the_filter_never_improves_the_number(
    graded_reference: ReferenceGenome,
) -> None:
    """The failure direction, asserted as an inequality rather than an equality.

    Stated separately from the equality above because this is the property that would
    matter if the tail ever became approximate: showing less must never score better.
    """
    reports = _reports(graded_reference)
    loosest = reports[0].specificity_score()
    for threshold, report in zip(THRESHOLDS, reports, strict=True):
        assert report.specificity_score() <= loosest + 1e-9, (
            f"threshold {threshold} scores better than showing everything: "
            f"{report.specificity_score()} > {loosest}"
        )
