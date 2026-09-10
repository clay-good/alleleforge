"""A declared field is not a filled field.

The guard written for the cohort envelope's run-level notes constructed a `BatchResponse`
itself, gave it the notes, and asserted they serialized — which they do, being a field.
Deleting the line in `_cohort_response` that *fills* the field left that guard green, and
the endpoint kept returning an empty list. The test had assumed the bug away.

This is the derived form of that lesson, and it costs one AST walk: for every response
model the API constructs, a field with a default that **no construction site ever passes**
can only ever be its default. That is either dead weight in the schema or — the case this
comes from — a disclosure a client is being promised and never given.

Fields legitimately left to their default are recorded with the reason, and the list is
short enough to read, which is this project's test for whether a derivation is honest.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from alleleforge.web.api import models as models_module  # noqa: E402

_APP = Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "api" / "app.py"
_MODELS = Path(models_module.__file__)

#: Fields whose default *is* the answer, with why. A response model is also a request
#: model's neighbour here, so `model -> field`.
_DEFAULT_IS_THE_ANSWER: dict[str, set[str]] = {
    # Stamped by the response model itself from a module constant, not by the endpoint:
    # every locus in the document is in that convention by construction, so passing it
    # per response would be a chance to pass the wrong one.
    "BatchResponse": {"coordinate_system"},
    # Same shape as the convention above: the research-use sentence is a property of the
    # document, not of the run, so the model stamps it. (`BatchResponse` passes its own
    # rather than defaulting it — two coherent choices for one field across two models,
    # which is worth an exception line and not worth a refactor.)
    "OffTargetResponse": {"coordinate_system", "disclaimer"},
    "ResolveResponse": {"coordinate_system"},
}


def _response_models() -> dict[str, set[str]]:
    """Field names per response model, from the module's own class definitions."""
    tree = ast.parse(_MODELS.read_text(encoding="utf-8"))
    out: dict[str, set[str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or not node.name.endswith("Response"):
            continue
        out[node.name] = {
            stmt.target.id
            for stmt in node.body
            if isinstance(stmt, ast.AnnAssign)
            and isinstance(stmt.target, ast.Name)
            and stmt.value is not None  # has a default; without one it must be passed
        }
    return {name: fields for name, fields in out.items() if fields}


def _assigned_keywords(model: str) -> set[str]:
    """Keyword names passed when ``model`` is constructed.

    Both spellings: `OffTargetResponse(...)` from the app, and `cls(...)` inside the
    model's own `from_report` classmethod — which is how most of them are actually built,
    and missing it made the first version of this guard report every field of that model.
    """
    assigned: set[str] = set()
    for path in (_APP, _MODELS):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == model:
                for inner in ast.walk(node):
                    if (
                        isinstance(inner, ast.Call)
                        and isinstance(inner.func, ast.Name)
                        and inner.func.id in {"cls", model}
                    ):
                        assigned |= {kw.arg for kw in inner.keywords if kw.arg}
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == model
            ):
                assigned |= {kw.arg for kw in node.keywords if kw.arg}
    return assigned


def test_the_derivation_finds_models_and_defaults() -> None:
    """A scan that matched nothing would pass the check below for the wrong reason."""
    found = _response_models()
    assert "BatchResponse" in found, found
    assert "notes" in found["BatchResponse"]


@pytest.mark.parametrize("model", sorted(_response_models()))
def test_every_defaulted_field_is_filled_somewhere(model: str) -> None:
    fields = _response_models()[model]
    never = fields - _assigned_keywords(model) - _DEFAULT_IS_THE_ANSWER.get(model, set())
    assert not never, (
        f"{model} declares {sorted(never)} and no code ever passes them, so a client is "
        "promised a field that can only ever be its default. Fill it where the response "
        "is built, or record it in _DEFAULT_IS_THE_ANSWER with the reason."
    )
