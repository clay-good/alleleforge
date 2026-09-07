"""`calibrated=False` qualifies the interval. Nothing qualified the number.

A report printed:

    Efficiency 0.60 [0.45, 0.75] @ 80% (nominal — coverage not measured)

The parenthetical is about the *band*. The point estimate came from an unfitted
pseudo-random scaffold, and the bundled model card says so as its load-bearing sentence —
"the heads are an unfitted pseudo-random scaffold: the point estimate is not a trained
activity prediction (method=HEURISTIC)". `Prediction.point_from_trained_model` records it
per prediction, is asserted by the scoring tests, and reached no human surface: the number
was rendered in exactly the typography a trained model's estimate would get.

A reader who takes one number from this artifact takes the point estimate. It now carries
its own provenance, on both human renders and for every prediction that has one —
efficiency and P(intended) alike — and a trained prediction is left unadorned so the note
means something when it appears.
"""

from __future__ import annotations

import re

import pytest

from alleleforge.report.builder import build_report
from alleleforge.report.html import render_html
from alleleforge.report.pdf import render_pdf
from alleleforge.types.candidate import DesignCandidate, RankedMenu
from alleleforge.types.edit import Chemistry
from alleleforge.types.guide import PAM, Guide, Spacer
from alleleforge.types.prediction import Prediction, UncertaintyMethod
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand

_MARKER = "not from a trained model"


def _prediction(*, trained: bool) -> Prediction[float]:
    return Prediction[float](
        value=0.60,
        interval=(0.45, 0.75),
        interval_level=0.8,
        method=UncertaintyMethod.ENSEMBLE if trained else UncertaintyMethod.HEURISTIC,
        calibrated=False,
        point_from_trained_model=trained,
    )


def _menu(*, trained: bool) -> RankedMenu:
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
        efficiency=_prediction(trained=trained),
        rationale="fixture",
    )
    return RankedMenu(candidates=(candidate,), rationale="fixture")


def test_an_untrained_estimate_is_marked_on_both_renders() -> None:
    report = build_report(_menu(trained=False))
    assert _MARKER in render_html(report)
    assert _MARKER in render_pdf(report).decode("latin-1", errors="ignore")


def test_a_trained_estimate_is_left_unadorned() -> None:
    """A note that appears on everything says nothing."""
    report = build_report(_menu(trained=True))
    assert _MARKER not in render_html(report)
    assert _MARKER not in render_pdf(report).decode("latin-1", errors="ignore")


def test_the_note_names_the_method() -> None:
    html = render_html(build_report(_menu(trained=False)))
    assert "heuristic point estimate" in html


def test_it_is_distinct_from_the_interval_caveat() -> None:
    """Two different claims: the band's coverage, and the number's provenance."""
    html = render_html(build_report(_menu(trained=False)))
    line = re.search(r"<p>Efficiency.*?</p>", html, re.S)
    assert line is not None
    assert "coverage not measured" in line.group(0)
    assert _MARKER in line.group(0)


@pytest.mark.parametrize("trained", [True, False])
def test_the_flag_survives_the_report_boundary(trained: bool) -> None:
    """The builder must carry the prediction, not a flattened float."""
    report = build_report(_menu(trained=trained))
    efficiency = report.candidates[0].efficiency
    assert efficiency is not None
    assert efficiency.point_from_trained_model is trained
