"""Every reagent type in `types/guide.py` declares itself frozen; nothing checked it.

A designed reagent is passed through scoring, ranking, rendering, and oligo assembly, and
each of those reads the same object. `frozen=True` on all ten models in this module is
what makes that safe: a stage cannot quietly retune a spacer, a nick offset, or a donor's
re-cut disposition for the stages after it. A mutation sweep flipped `frozen=True` to
`False` on every one of them with the suite green, because immutability is the kind of
property every test relies on and none states. The web API's models already have this
guard; the reagents themselves did not.

Written against the module's public models rather than a hand-kept list, so a type added
later is covered the day it is added.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from alleleforge.types import guide


def _models() -> list[type[BaseModel]]:
    found = [
        obj
        for name, obj in vars(guide).items()
        if isinstance(obj, type)
        and issubclass(obj, BaseModel)
        and obj is not BaseModel
        and obj.__module__ == guide.__name__
        and not name.startswith("_")
    ]
    assert found, "no models discovered; this test would pass vacuously"
    return found


def test_the_module_still_has_the_reagent_types_this_covers() -> None:
    names = {m.__name__ for m in _models()}
    # Named explicitly so a type that stops being a model, or is renamed, is noticed
    # here rather than silently dropping out of the sweep below.
    assert {
        "PAM",
        "Spacer",
        "Guide",
        "BaseEditWindow",
        "NickingGuide",
        "PegRNA",
        "BlockingMutation",
        "HDRDonor",
    } <= names


@pytest.mark.parametrize("model", _models(), ids=lambda m: m.__name__)
def test_a_guide_type_refuses_assignment(model: type[BaseModel]) -> None:
    assert model.model_config.get("frozen") is True, (
        f"{model.__name__} is no longer frozen; a later pipeline stage can retune a "
        "reagent the earlier stages already scored and rendered"
    )
    field = next(iter(model.model_fields))
    instance = model.model_construct()
    with pytest.raises(ValidationError, match="frozen"):
        setattr(instance, field, None)
