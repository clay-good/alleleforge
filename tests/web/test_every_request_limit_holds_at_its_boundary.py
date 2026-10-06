"""Every size limit a request model advertises is enforced exactly at its value.

The per-field caps in `web/api/models.py` are the request-size bound the web-API
hardening promised, and seven of the ten were never named by a test. A constant-mutation
sweep could move any of them without a failure. Moving a configured limit is not itself
a defect, but an unenforced or off-by-one one is. So this file does not pin the numbers.
It reads every `maxLength` and `maxItems` the published JSON schema advertises and checks
the model on both sides of each: a value *at* the limit raises no size error, and one
*past* it is refused at that field. A limit added later is covered without editing this
file, and a schema that advertises a bound the model does not apply fails here.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from alleleforge.web.api.models import (
    BatchRequest,
    DesignRequest,
    OffTargetRequest,
    Region,
    ResolveRequest,
)

_MODELS: tuple[type[BaseModel], ...] = (
    ResolveRequest,
    DesignRequest,
    BatchRequest,
    Region,
    OffTargetRequest,
)
_SIZE_ERRORS = {"string_too_long", "too_long"}


def _concrete(prop: dict[str, Any]) -> dict[str, Any]:
    """Return the non-null branch of an `Optional[...]` schema."""
    for branch in prop.get("anyOf", ()):
        if branch.get("type") != "null":
            return dict(branch)
    return prop


def _limits() -> list[tuple[type[BaseModel], str, str, int]]:
    """Return ``(model, field, kind, limit)`` for every advertised size bound."""
    out: list[tuple[type[BaseModel], str, str, int]] = []
    for model in _MODELS:
        for name, prop in model.model_json_schema()["properties"].items():
            prop = _concrete(prop)
            if "maxLength" in prop:
                out.append((model, name, "string", prop["maxLength"]))
            if "maxItems" in prop:
                out.append((model, name, "list", prop["maxItems"]))
            item = prop.get("items", {})
            if isinstance(item, dict) and "maxLength" in item:
                out.append((model, name, "item", item["maxLength"]))
    return out


def _value(kind: str, n: int) -> Any:
    return {"string": "A" * n, "list": ["A"] * n, "item": ["A" * n]}[kind]


def _size_error_at(model: type[BaseModel], field: str, kind: str, value: Any) -> bool:
    try:
        model.model_validate({field: value})
    except ValidationError as exc:
        loc = (field, 0) if kind == "item" else (field,)
        return any(e["type"] in _SIZE_ERRORS and e["loc"] == loc for e in exc.errors())
    return False


_ALL = _limits()


def test_the_schema_advertises_the_limits_this_file_is_about() -> None:
    # Premise: the walk found the caps, including list and list-item ones. If the schema
    # shape changed and this found nothing, every test below would pass vacuously.
    kinds = {kind for _, _, kind, _ in _ALL}
    assert len(_ALL) >= 20 and kinds == {"string", "list", "item"}, _ALL


@pytest.mark.parametrize(
    ("model", "field", "kind", "limit"),
    _ALL,
    ids=[f"{m.__name__}.{f}:{k}" for m, f, k, _ in _ALL],
)
def test_a_limit_admits_its_value_and_refuses_one_more(
    model: type[BaseModel], field: str, kind: str, limit: int
) -> None:
    assert not _size_error_at(model, field, kind, _value(kind, limit))
    assert _size_error_at(model, field, kind, _value(kind, limit + 1))


_RANGE_ERRORS = {"greater_than_equal", "less_than_equal", "greater_than", "less_than"}


def _bounds() -> list[tuple[type[BaseModel], str, str, float, bool]]:
    """Return ``(model, field, side, bound, integer)`` for every numeric bound."""
    out: list[tuple[type[BaseModel], str, str, float, bool]] = []
    for model in _MODELS:
        for name, prop in model.model_json_schema()["properties"].items():
            prop = _concrete(prop)
            integer = prop.get("type") == "integer"
            for side in ("minimum", "maximum"):
                if side in prop:
                    out.append((model, name, side, prop[side], integer))
    return out


def _range_error_at(model: type[BaseModel], field: str, value: float) -> bool:
    try:
        model.model_validate({field: value})
    except ValidationError as exc:
        return any(e["type"] in _RANGE_ERRORS and e["loc"] == (field,) for e in exc.errors())
    return False


_BOUNDS = _bounds()


@pytest.mark.parametrize(
    ("model", "field", "side", "bound", "integer"),
    _BOUNDS,
    ids=[f"{m.__name__}.{f}:{s}" for m, f, s, _, _ in _BOUNDS],
)
def test_a_numeric_bound_admits_its_value_and_refuses_the_next(
    model: type[BaseModel], field: str, side: str, bound: float, integer: bool
) -> None:
    step = 1 if integer else 1e-6
    past = bound - step if side == "minimum" else bound + step
    assert not _range_error_at(model, field, bound)
    assert _range_error_at(model, field, past)


def test_the_walk_found_numeric_bounds_on_both_sides() -> None:
    assert {side for _, _, side, _, _ in _BOUNDS} == {"minimum", "maximum"}, _BOUNDS


def test_every_api_model_is_immutable() -> None:
    """Requests are read by handlers and responses are cached and serialized; neither
    may change underneath its reader. The policy is uniform across the module, so it
    is checked across the module rather than per class."""
    import inspect

    import alleleforge.web.api.models as api

    models = [
        cls
        for _, cls in inspect.getmembers(api, inspect.isclass)
        if issubclass(cls, BaseModel) and cls.__module__ == api.__name__
    ]
    assert len(models) > 10
    assert [m.__name__ for m in models if not m.model_config.get("frozen")] == []
    region = Region(chrom="chr2", start=1, end=5)
    with pytest.raises(ValidationError, match="frozen"):
        region.start = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    ("model", "field", "low", "high"),
    [
        # Probabilities and scores: [0, 1] is what the quantity is, not a tuning choice.
        (OffTargetRequest, "cfd_threshold", 0.0, 1.0),
        (OffTargetRequest, "mit_threshold", 0.0, 1.0),
        (OffTargetRequest, "maf", 0.0, 1.0),
        # Genomic coordinates are non-negative.
        (Region, "start", 0, None),
        (Region, "end", 0, None),
        # A per-chemistry cap of 0 would keep nothing; the smallest real cap is 1.
        (DesignRequest, "max_per_chemistry", 1, None),
        (BatchRequest, "max_per_chemistry", 1, None),
    ],
)
def test_a_bound_that_follows_from_the_quantity_is_exactly_that_bound(
    model: type[BaseModel], field: str, low: float, high: float | None
) -> None:
    prop = _concrete(model.model_json_schema()["properties"][field])
    assert prop.get("minimum") == low
    assert prop.get("maximum") == high
