"""A whole paragraph of numbers could vanish from the on-screen report, suite green.

`test_every_report_field_is_rendered` is the guard this project built for "a field
nothing reads", and it is a **static** one: it greps the renderer's source for each
field name. That catches a field no renderer mentions. It cannot catch a field a
renderer mentions **twice** and renders once — and `_candidate_html` renders
`p_intended` from two branches, one for a derived figure and one for a calibrated
prediction. Delete either `parts.append(...)` and the name is still in the file, so the
static check passes while half the reports lose the number a reader is most likely to
act on.

A statement-deletion sweep removed nine `parts.append` calls from `report/html.py` one
at a time, and the whole suite stayed green for every one: the bystander-burden
paragraph, both P(intended) paragraphs, the outcome-allele table, the oligo-prep
instruction, the "no synthesized reagent" line, the ranking rationale, the closing
`</div>`, and the genomic-context note.

So this file renders a candidate that carries **every** optional value and asserts each
one reaches the screen — behaviour, not a grep. It is the pair to the static check, not
a replacement: that one covers fields that do not exist yet, this one covers the
branches a field is rendered through.
"""

from __future__ import annotations

import pytest

from alleleforge.report.builder import CandidateReport
from alleleforge.report.html import _candidate_html
from alleleforge.report.oligos import LENTIGUIDE_BSMBI, sgrna_oligos
from alleleforge.types.edit import AlleleOutcome, Chemistry
from alleleforge.types.prediction import Prediction, UncertaintyMethod

_SPACER = "ACGTACGTACGTACGTACGT"


def _prediction(value: float) -> Prediction[float]:
    return Prediction[float](
        value=value,
        interval=(round(value - 0.1, 2), round(value + 0.1, 2)),
        interval_level=0.8,
        method=UncertaintyMethod.HEURISTIC,
    )


def _candidate(**overrides: object) -> CandidateReport:
    base: dict[str, object] = {
        "rank": 1,
        "chemistry": Chemistry.CAS9_NUCLEASE,
        "on_pareto_front": True,
        "reagent": "sgRNA candidate 1",
        "efficiency": _prediction(0.50),
        "bystander_burden": _prediction(0.30),
        "p_intended": 0.44,
        "p_intended_prediction": None,
        "outcome_top": (
            AlleleOutcome(allele="ACGTTTTT", probability=0.421, is_intended=True),
            AlleleOutcome(allele="ACGTTTTA", probability=0.117),
        ),
        "n_outcome_alleles": 2,
        "outcome_shown_mass": 0.538,
        "n_offtarget_sites": None,
        "offtarget_specificity": None,
        "offtarget_by_ancestry": (),
        "oligos": sgrna_oligos(_SPACER, scheme=LENTIGUIDE_BSMBI, kind="sgrna"),
        "oligos_requested": True,
        "flags": (),
        "rationale": "ranked first on a distinctive rationale sentence",
    }
    return CandidateReport(**{**base, **overrides})  # type: ignore[arg-type]


def test_the_fixture_carries_the_values_this_file_is_about() -> None:
    """The premise: an absent value cannot prove a renderer drops a present one."""
    c = _candidate()
    assert c.bystander_burden is not None
    assert c.p_intended is not None
    assert c.outcome_top and c.oligos is not None
    assert c.oligos.scheme.phosphorylation, "the oligo-prep line needs a scheme that has one"


def test_the_bystander_burden_and_its_interval_reach_the_screen() -> None:
    html = _candidate_html(_candidate())
    assert "Bystander burden" in html
    assert "0.30" in html and "[0.20, 0.40]" in html


def test_a_derived_p_intended_reaches_the_screen() -> None:
    """The branch taken when the outcome predictor made no prediction for it."""
    html = _candidate_html(_candidate(p_intended_prediction=None))
    assert "P(intended)" in html
    assert "0.44" in html
    assert "derived from the outcome distribution" in html


def test_a_predicted_p_intended_reaches_the_screen() -> None:
    """The other branch — the one the static field check cannot tell apart."""
    html = _candidate_html(_candidate(p_intended_prediction=_prediction(0.44)))
    assert "P(intended)" in html
    assert "0.44" in html and "[0.34, 0.54]" in html
    assert "derived from the outcome distribution" not in html


def test_every_outcome_allele_reaches_the_screen() -> None:
    html = _candidate_html(_candidate())
    assert "<table" in html
    for allele in ("ACGTTTTT", "ACGTTTTA"):
        assert allele in html, allele
    assert "0.421" in html and "0.117" in html


def test_the_oligo_prep_instruction_reaches_the_screen() -> None:
    candidate = _candidate()
    assert candidate.oligos is not None
    html = _candidate_html(candidate)
    assert "oligo prep" in html
    assert candidate.oligos.scheme.phosphorylation.split()[0] in html


def test_a_candidate_that_needs_no_oligos_says_so() -> None:
    """The `elif` branch: oligos were asked for and this reagent needs none."""
    html = _candidate_html(_candidate(oligos=None, oligos_requested=True))
    assert "none required" in html


def test_the_rationale_reaches_the_screen() -> None:
    html = _candidate_html(_candidate())
    assert "ranked first on a distinctive rationale sentence" in html


@pytest.mark.parametrize("oligos_requested", [True, False])
def test_the_candidate_block_closes_every_division_it_opens(oligos_requested: bool) -> None:
    """A dropped `</div>` leaves the rest of the page nested inside this candidate."""
    html = _candidate_html(_candidate(oligos_requested=oligos_requested))
    assert html.count("<div") == html.count("</div>"), html[-200:]


def test_the_page_tells_a_reader_how_to_see_the_loci(prime_menu: object) -> None:
    """The one page-level `append` the sweep reached, and the only route it names.

    The report draws its own charts but shows no genome browser, and this sentence is
    where it says what to do about that. It is the kind of line that reads as filler
    and is the only answer a reader has to "where do I look at this in context" — and
    nothing asserted it was on the page.
    """
    from alleleforge.report.builder import build_report
    from alleleforge.report.html import render_html

    page = render_html(build_report(prime_menu))  # type: ignore[arg-type]
    assert "Genomic context" in page
    assert "jbrowse.org" in page
