"""A field on a report model must reach at least one thing a person reads.

The recurring defect in this codebase is not a wrong number — it is a correct one
that no surface shows. `search_description()` was computed and dropped by the web
envelope; the CFD citation lived in a docstring; `sources_considered` and
`unbacked_populations` were each added to answer a question a reader was asking and
then had to be wired to a render separately.

`project.md` prescribes the guard: *"A test that iterates `Model.model_fields`
instead of naming fields covers the fields that do not exist yet."* `Provenance` and
`OffTargetReport` have one. The two models a reader actually reads did not — and two
fields were added to `CandidateReport` in recent work with nothing to notice if either
had been left unrendered.

This is a static check: it asserts each field is *referenced* by a renderer, not that
the value is correct or well-placed. That is deliberately weak and deliberately cheap;
it catches the one failure that keeps recurring, which is a field nothing reads.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import BaseModel

from alleleforge.report.builder import CandidateReport, DesignReport
from alleleforge.report.oligos import PegRNAOligos, SgRnaOligos

_RENDERERS = ("html.py", "pdf.py", "export.py")

#: Fields that legitimately reach no renderer, each with the reason. A field may only
#: be here with an explanation, so this cannot become a place to hide a dropped field.
_NOT_RENDERED: dict[str, str] = {
    "coordinate_system": (
        "the machine-readable spelling of a fact the prose renders already state in "
        "words (COORDINATE_NOTE, in the footer). It exists for the JSON export, which "
        "serializes every field wholesale and so never names this one; both come from "
        "COORDINATE_SYSTEM, and test_every_surface_states_the_same_facts checks the "
        "convention reaches all four surfaces"
    ),
}


def _renderer_sources() -> dict[str, str]:
    root = Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "report"
    return {name: (root / name).read_text() for name in _RENDERERS}


def _unreferenced(model: type[BaseModel], receivers: tuple[str, ...]) -> list[str]:
    """Return fields of ``model`` no renderer mentions on any of ``receivers``."""
    sources = _renderer_sources()
    alternatives = "|".join(receivers)
    return [
        field
        for field in model.model_fields
        if field not in _NOT_RENDERED
        and not any(re.search(rf"\b(?:{alternatives})\.{field}\b", src) for src in sources.values())
    ]


@pytest.mark.parametrize(
    ("model", "receivers"),
    [(CandidateReport, ("c", "candidate")), (DesignReport, ("r", "report"))],
    ids=["CandidateReport", "DesignReport"],
)
def test_every_field_reaches_a_renderer(model: type[BaseModel], receivers: tuple[str, ...]) -> None:
    assert model.model_fields, "no fields discovered — the introspection is wrong"
    missing = _unreferenced(model, receivers)
    assert not missing, (
        f"{model.__name__} fields that no renderer reads: {missing}. Render them, or "
        "record them in _NOT_RENDERED with the reason a reader does not need them."
    )


def test_the_check_would_notice_an_unrendered_field() -> None:
    """Guard the guard: a field name absent from every renderer must be reported."""

    class Sample(BaseModel):
        offtarget_specificity: float = 0.0  # really is rendered
        a_field_no_renderer_mentions: int = 0

    assert _unreferenced(Sample, ("c", "candidate")) == ["a_field_no_renderer_mentions"]


def test_documented_exceptions_are_real_fields() -> None:
    """An allowance must not outlive the field it excuses."""
    known = set(CandidateReport.model_fields) | set(DesignReport.model_fields)
    stale = sorted(set(_NOT_RENDERED) - known)
    assert not stale, f"_NOT_RENDERED lists fields that no longer exist: {stale}"


#: Oligo fields the PDF's hand-formatted block legitimately omits, each with the reason.
#: Checked against the PDF specifically: the HTML dumps the whole oligo record as JSON,
#: so every field is trivially "present" there and nothing is learned — while the
#: hand-formatted view is the one a lab orders from, and is where a field goes missing.
#: It did: `donor` was absent, so the printable sheet listed the guide duplex and not
#: the repair template that makes a precise edit possible.
_OLIGO_NOT_IN_PDF: dict[str, str] = {
    "kind": "the block's own heading names the scheme and the donor kind",
    "rtt": "encoded in the ext duplex that is actually ordered",
    "pbs": "encoded in the ext duplex that is actually ordered",
    "motif": "encoded in the ext duplex that is actually ordered",
    "scaffold": "supplied by the vector, not ordered as an oligo",
}


@pytest.mark.parametrize("model", [SgRnaOligos, PegRNAOligos], ids=lambda m: m.__name__)
def test_every_oligo_field_reaches_the_printable_sheet(model: type[BaseModel]) -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "report"
    pdf = (root / "pdf.py").read_text()
    # Plain substring checks: the receiver in that block is always `oligos` or
    # `donor`, and a regex built by f-string interpolation matched nothing here
    # while working standalone — a checker that silently finds nothing is worse
    # than no checker at all.
    missing = [
        field
        for field in model.model_fields
        if field not in _OLIGO_NOT_IN_PDF
        and f"oligos.{field}" not in pdf
        and f"donor.{field}" not in pdf
    ]
    assert not missing, (
        f"{model.__name__} fields absent from the printable order sheet: {missing}. "
        "Render them, or record them in _OLIGO_NOT_IN_PDF with the reason."
    )


def test_the_oligo_allowances_are_real_fields() -> None:
    known = set(SgRnaOligos.model_fields) | set(PegRNAOligos.model_fields)
    stale = sorted(set(_OLIGO_NOT_IN_PDF) - known)
    assert not stale, f"_OLIGO_NOT_IN_PDF lists fields that no longer exist: {stale}"
