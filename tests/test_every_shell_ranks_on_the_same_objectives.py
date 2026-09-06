"""The ranker declares the objectives; every shell has to spell them from that.

`design.ranking.OBJECTIVES` names the four axes a candidate is scored on. The CLI held
its own copy (`_WEIGHT_AXES`), and the web API held two more — a hardcoded
`min_length=4` / `max_length=4` on the request field and a positional
`e, c, s, p = weights_in` unpack. Four spellings of one fact.

They agreed, and the risk is not that they drift into disagreement about the four we
have. It is that a fifth objective becomes unreachable from every shell at once, and
worse than unreachable: the CLI would refuse the very table naming it ("must name
exactly [the four]") and the web API would reject the five-element vector as too long.
This is the R63-76 class — a capability the library has that no shell can reach — except
it would arrive with the shells actively contradicting the library.

The shells now derive from `OBJECTIVES`. What is left to pin is the pair that still
cannot derive: `RankingWeights` declares its axes as dataclass fields, and `OBJECTIVES`
is a hand-written tuple of those field names. `__post_init__` and `normalized()` reach
them with `getattr`, so a renamed field turns into an `AttributeError` at call time
rather than an import error.
"""

from __future__ import annotations

import dataclasses

import pytest
import typer
from fastapi.testclient import TestClient

from alleleforge.design.ranking import DEFAULT_WEIGHTS, OBJECTIVES, RankingWeights


def test_the_objective_list_matches_the_weights_it_names() -> None:
    """The one pair that cannot be derived: the tuple and the dataclass fields."""
    assert tuple(f.name for f in dataclasses.fields(RankingWeights)) == OBJECTIVES


def test_the_declared_objectives_are_all_reachable_by_getattr() -> None:
    """`normalized()` and `__post_init__` read every objective off the instance."""
    assert set(DEFAULT_WEIGHTS.normalized()) == set(OBJECTIVES)


def test_the_cli_names_every_objective_when_it_refuses_a_table() -> None:
    from alleleforge.cli.main import _parse_weights

    with pytest.raises(typer.Exit):
        _parse_weights({name: 1.0 for name in OBJECTIVES[:-1]})


def test_the_cli_accepts_exactly_as_many_numbers_as_there_are_objectives() -> None:
    from alleleforge.cli.main import _parse_weights

    parsed = _parse_weights(",".join("1" for _ in OBJECTIVES))
    assert parsed.normalized() == {name: 1 / len(OBJECTIVES) for name in OBJECTIVES}


def test_the_web_schema_sizes_its_weight_vector_from_the_objectives() -> None:
    """A hardcoded 4 here would silently cap the API a fifth objective needs."""
    from alleleforge.web.api.app import create_app

    schema = TestClient(create_app()).get("/openapi.json").json()
    # Request models only: the response model's `weights` is the normalized name->value
    # map the run actually used, not a vector the caller supplies.
    fields = [
        props["weights"]
        for name, model in schema["components"]["schemas"].items()
        if name.endswith("Request")
        for props in (model.get("properties", {}),)
        if "weights" in props
    ]
    assert fields, "no request model exposes a weights vector"
    for field in fields:
        vector = next(
            (variant for variant in field.get("anyOf", [field]) if variant.get("type") == "array"),
            None,
        )
        assert vector is not None, field
        assert vector["minItems"] == vector["maxItems"] == len(OBJECTIVES)
        for name in OBJECTIVES:
            assert name in field.get("description", "")
