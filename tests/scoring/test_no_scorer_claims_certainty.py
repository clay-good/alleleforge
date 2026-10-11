"""No efficiency scorer ever returns 0 or 1: a prediction is never a certainty.

Both efficiency heads squash their logit through a logistic clamped to ``[0.01, 0.99]``,
and both say so in the same sentence of their own docstring. The clamp is the reason a
score of exactly 1.0 — "this guide always works" — cannot leave this library, which
matters because the number is ranked, printed, and read as a probability.

A constant pass moved the upper bound to 1.089 and the lower to 0.011 with the suite green
in both modules: every fixture scored a middling guide, so the logistic never came near
either rail and the clamp was never the thing that decided the answer. Testing it needs a
logit far enough out that the unclamped logistic would round to a certainty.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.scoring import cas9_efficiency, prime_efficiency

_MODULES = [cas9_efficiency, prime_efficiency]
_IDS = [m.__name__.rsplit(".", 1)[1] for m in _MODULES]


@pytest.mark.parametrize("module", _MODULES, ids=_IDS)
def test_an_extreme_logit_is_held_below_certainty(module: object) -> None:
    sigmoid = module._sigmoid  # type: ignore[attr-defined]
    # +-50 is far past where the unclamped logistic rounds to 0 or 1 (1 - 2e-22), and
    # well inside `math.exp`'s range: the helper raises OverflowError below about -710,
    # which no shipped path can reach (the prime logit bottoms out near -2.3 and the
    # ensemble's dot product is bounded by its 16 unit-scale terms), so it is left alone
    # rather than given error handling for an unreachable input.
    assert sigmoid(50.0) == 0.99, "a saturating logit must still not be a certainty"
    assert sigmoid(-50.0) == 0.01, "nor must the floor be an impossibility"
    assert sigmoid(0.0) == pytest.approx(0.5), "the logistic itself must be intact"


@pytest.mark.parametrize("module", _MODULES, ids=_IDS)
def test_the_clamp_is_monotone_up_to_its_rails(module: object) -> None:
    """A clamp that preserved order would be useless if it inverted anywhere."""
    sigmoid = module._sigmoid  # type: ignore[attr-defined]
    values = [sigmoid(x) for x in (-12.0, -3.0, -1.0, 0.0, 1.0, 3.0, 12.0)]
    assert values == sorted(values)
    assert min(values) >= 0.01 and max(values) <= 0.99


@pytest.mark.parametrize("module", _MODULES, ids=_IDS)
def test_the_docstring_still_states_the_bounds_it_enforces(module: object) -> None:
    """The sentence a reader trusts, bound to the numbers the code applies."""
    doc = module._sigmoid.__doc__ or ""  # type: ignore[attr-defined]
    assert "clamped to ``[0.01, 0.99]``" in doc, (
        "the stated bounds no longer match; a reader is told the wrong envelope"
    )
    source = Path(module.__file__).read_text(encoding="utf-8")  # type: ignore[attr-defined]
    assert "min(0.99, max(0.01," in source
