"""Both renders kept their own list of which predictions to read notes from.

`_uncovered_notes` existed twice — once in `html.py`, once in `pdf.py` — and both copies
named `efficiency` and `bystander_burden`. Neither named `p_intended_prediction`, so a
note attached to the intended-allele probability would have reached the JSON and no human
page. Today that prediction carries only the nominal-interval note, which is deduplicated
anyway, so nothing was lost yet: the bug was latent, in duplicate.

The rule is one shared function now, and the list is derived from the model rather than
maintained, so a prediction field added later is covered the day it appears.
"""

from __future__ import annotations

from alleleforge.report.builder import (
    CandidateReport,
    build_report,
    candidate_predictions,
    uncovered_prediction_notes,
)
from alleleforge.report.html import render_html
from alleleforge.report.pdf import render_pdf
from alleleforge.types.candidate import DesignCandidate, RankedMenu
from alleleforge.types.edit import AlleleOutcome, Chemistry, EditOutcome
from alleleforge.types.guide import PAM, Guide, Spacer
from alleleforge.types.prediction import (
    NOMINAL_INTERVAL_NOTE,
    Prediction,
    UncertaintyMethod,
)
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand

_ODD_NOTE = "this quantity is a spread, not a coverage band"


def _prediction(*notes: str) -> Prediction[float]:
    return Prediction[float](
        value=0.5,
        interval=(0.4, 0.6),
        interval_level=0.8,
        method=UncertaintyMethod.HEURISTIC,
        notes=(NOMINAL_INTERVAL_NOTE, *notes),
    )


def _menu() -> RankedMenu:
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
        efficiency=_prediction(),
        # `p_intended_prediction` is derived only when an outcome exists — the report
        # takes the distribution's own p(intended) and the prediction that carries its
        # interval, so a candidate with no outcome legitimately has neither.
        outcome=EditOutcome(
            alleles=(
                AlleleOutcome(allele="+1", probability=0.6, is_intended=True),
                AlleleOutcome(allele="-2", probability=0.4),
            )
        ),
        p_intended=_prediction(_ODD_NOTE),
        rationale="fixture",
    )
    return RankedMenu(candidates=(candidate,), rationale="fixture")


def test_the_prediction_list_is_derived_not_maintained() -> None:
    """Every `Prediction` field on the rendered candidate, found from the model."""
    report = build_report(_menu())
    prediction_fields = {
        name
        for name in CandidateReport.model_fields
        if isinstance(getattr(report.candidates[0], name), Prediction)
    }
    assert len(candidate_predictions(report.candidates[0])) == len(prediction_fields)
    assert "p_intended_prediction" in prediction_fields


def test_a_note_on_the_intended_probability_reaches_both_renders() -> None:
    """The field neither hand-written list named."""
    report = build_report(_menu())
    assert _ODD_NOTE in uncovered_prediction_notes(report.candidates[0])
    assert _ODD_NOTE in render_html(report)
    assert _ODD_NOTE in render_pdf(report).decode("latin-1", errors="ignore")


def test_the_inline_caveat_is_still_not_repeated() -> None:
    """The nominal-interval note is already spelled out beside the interval."""
    report = build_report(_menu())
    assert NOMINAL_INTERVAL_NOTE not in uncovered_prediction_notes(report.candidates[0])


def test_both_renders_use_the_same_rule() -> None:
    """It was two copies of one list; a shared helper is what keeps them equal."""
    import inspect

    from alleleforge.report import html, pdf

    for module in (html, pdf):
        source = inspect.getsource(module)
        assert "uncovered_prediction_notes(" in source
        assert "def _uncovered_notes" not in source
