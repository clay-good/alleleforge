"""The report's headline off-target number did not say which scale produced it.

A report carries no per-site rows by design — it summarises, and the lossless export has
the sites. On a table that mixes matrices the effective matrix reads
`doench-2016-cfd + doench-2016-seed-tolerance-approximation`, which tells a reader both
scales were used and not which one produced the number they are acting on. The worst-case
score *is* that number: it drives the safety axis, the ancestry table and the triage
decision.

So the one site whose score a reader takes away names its own matrix, and only when the
report actually mixes them — on a homogeneous table the effective matrix already says it
once, and repeating it is noise.
"""

from __future__ import annotations

from alleleforge.report.builder import build_report
from alleleforge.report.export import report_to_json, report_to_tsv
from alleleforge.report.html import render_html
from alleleforge.report.pdf import render_pdf
from alleleforge.types.candidate import DesignCandidate, RankedMenu
from alleleforge.types.edit import Chemistry
from alleleforge.types.guide import PAM, Guide, Spacer
from alleleforge.types.offtarget import (
    OffTargetReport,
    OffTargetSite,
    ScoreMethod,
)
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand

PUBLISHED = "doench-2016-cfd"
APPROXIMATION = "doench-2016-seed-tolerance-approximation"


def _site(score: float, matrix: str, start: int) -> OffTargetSite:
    return OffTargetSite(
        locus=GenomicInterval(chrom="chr2", start=start, end=start + 20, strand=Strand.PLUS),
        mismatches=1,
        score=score,
        score_method=ScoreMethod.CFD,
        score_matrix=matrix,
    )


def _menu(*sites: OffTargetSite) -> RankedMenu:
    guide = Guide(
        spacer=Spacer(sequence=DNASequence("ACGTAACGTTACGTAACGTT")),
        pam=PAM(pattern="NGG"),
        pam_sequence=DNASequence("TGG"),
        placement=GenomicInterval(chrom="chr1", start=10, end=30, strand=Strand.PLUS),
        cut_site=27,
    )
    candidate = DesignCandidate(
        chemistry=Chemistry.CAS9_NUCLEASE,
        guide=guide,
        offtarget=OffTargetReport(
            spacer="ACGTAACGTTACGTAACGTT",
            pam="NGG",
            scorer="CFD",
            score_matrix=PUBLISHED,
            sites=sites,
        ),
        rationale="fixture",
    )
    return RankedMenu(candidates=(candidate,), rationale="fixture")


def test_a_mixed_report_names_the_worst_site_s_matrix() -> None:
    report = build_report(_menu(_site(0.50, PUBLISHED, 100), _site(0.90, APPROXIMATION, 300)))
    assert report.candidates[0].offtarget_worst_matrix == APPROXIMATION


def test_it_is_the_worst_site_not_the_first() -> None:
    """Ordering must not decide it: the highest score is the one a reader acts on."""
    report = build_report(_menu(_site(0.90, APPROXIMATION, 300), _site(0.50, PUBLISHED, 100)))
    assert report.candidates[0].offtarget_worst_matrix == APPROXIMATION
    flipped = build_report(_menu(_site(0.90, PUBLISHED, 100), _site(0.50, APPROXIMATION, 300)))
    assert flipped.candidates[0].offtarget_worst_matrix == PUBLISHED


def test_a_homogeneous_report_says_nothing_extra() -> None:
    report = build_report(_menu(_site(0.50, PUBLISHED, 100), _site(0.90, PUBLISHED, 300)))
    assert report.candidates[0].offtarget_worst_matrix is None
    assert "worst site scored by" not in render_html(report)


def test_every_surface_carries_it() -> None:
    report = build_report(_menu(_site(0.50, PUBLISHED, 100), _site(0.90, APPROXIMATION, 300)))
    assert "worst site scored by" in render_html(report)
    assert "worst site scored by" in render_pdf(report).decode("latin-1", errors="ignore")
    assert "offtarget_worst_matrix" in report_to_tsv(report)
    assert APPROXIMATION in report_to_json(report)
