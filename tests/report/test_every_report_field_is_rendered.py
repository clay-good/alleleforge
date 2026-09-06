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

_RENDERERS = ("html.py", "pdf.py", "export.py")

#: Fields that legitimately reach no renderer, each with the reason. A field may only
#: be here with an explanation, so this cannot become a place to hide a dropped field.
_NOT_RENDERED: dict[str, str] = {}


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
