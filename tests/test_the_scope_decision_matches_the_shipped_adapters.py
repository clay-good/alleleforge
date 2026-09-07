"""The model-integration specs said which adapters were real, and nothing checked them.

`specs/cross-check-models-scope.md` is the decision record for every trained adapter:
one table names the four wired real models, a second names the five that are
placeholders on purpose, with the per-model evidence for each. `specs/` is linked from
the README, so this is what a reader consults to learn which predictions come from a
published model — the single most consequential thing this project claims.

It was prose. Its sibling `specs/base-outcome-integration.md` had already drifted the
other way: its header said implementation "is the next unit" for three months after its
own execution log recorded BE-DICT shipping, so a reader of the top of that document
got the opposite of what the bottom of it said.

This binds the decision to the code. A "supported" adapter must actually override the
gate's refusing forward pass; an "out of supported scope" one must not; and every
adapter the scoring package ships must appear in one list or the other, so the next one
added cannot be silently unclassified.
"""

from __future__ import annotations

import importlib
import inspect
import re
from pathlib import Path

_SCOPE = Path(__file__).resolve().parents[1] / "specs" / "cross-check-models-scope.md"

#: The scoring modules that define trained adapters, and the protocol method each
#: adapter's base refuses in. A "shipped" adapter is one that overrides it.
_MODULES = ("base_outcome", "cas9_outcome", "prime_efficiency", "pridict_engine")


def _adapters() -> dict[str, type]:
    found: dict[str, type] = {}
    for name in _MODULES:
        module = importlib.import_module(f"alleleforge.scoring.{name}")
        for attr, obj in vars(module).items():
            if (
                inspect.isclass(obj)
                and obj.__module__ == module.__name__
                and attr.endswith("Adapter")
                and not attr.startswith("_")
            ):
                found[attr] = obj
    assert found, "no trained adapters found — this check would be vacuous"
    return found


def _is_wired(adapter: type) -> bool:
    """Whether the adapter implements a forward pass rather than inheriting the refusal.

    Read off the resolved method, not the class body: every one of these subclasses
    inherits `_ModelZooAdapter`, whose `predict` resolves the license gate and then
    raises. A subclass is real exactly when it overrides that method with one that does
    not raise `NotImplementedError`.
    """
    for method in ("predict", "score", "design"):
        function = getattr(adapter, method, None)
        if function is None or not callable(function):
            continue
        try:
            source = inspect.getsource(function)
        except (OSError, TypeError):  # pragma: no cover - source always available here
            continue
        if "raise NotImplementedError" not in source:
            return True
    return False


def _documented() -> tuple[set[str], set[str]]:
    """Return (supported, out-of-scope) adapter names as the scope decision states them."""
    text = _SCOPE.read_text(encoding="utf-8")
    supported_table, _, rest = text.partition("out of supported\nscope")
    assert rest, "the scope decision no longer states which adapters are out of scope"
    supported = set(re.findall(r"\| `(\w+Adapter|\w+Scorer)` \|", supported_table))
    supported |= set(re.findall(r"\(`(\w+Adapter|\w+Scorer)`\)", supported_table))
    out_of_scope = set(re.findall(r"`(\w+Adapter)`", text)) - supported
    assert supported, "no supported models parsed from the scope decision"
    assert out_of_scope, "no out-of-scope adapters parsed from the scope decision"
    return supported, out_of_scope


def test_every_shipped_adapter_is_classified_by_the_scope_decision() -> None:
    supported, out_of_scope = _documented()
    unlisted = sorted(set(_adapters()) - supported - out_of_scope)
    assert not unlisted, (
        f"the scoring package ships {unlisted} and specs/cross-check-models-scope.md "
        "classifies neither as supported nor as out of scope. An adapter a reader "
        "cannot place is one whose predictions they cannot weigh."
    )


def test_a_supported_model_is_actually_wired() -> None:
    supported, _ = _documented()
    adapters = _adapters()
    for name in sorted(supported & set(adapters)):
        assert _is_wired(adapters[name]), (
            f"{name} is listed as a supported real model but still inherits the gate's "
            "refusing forward pass"
        )


def test_an_out_of_scope_adapter_is_still_a_placeholder() -> None:
    _, out_of_scope = _documented()
    adapters = _adapters()
    for name in sorted(out_of_scope & set(adapters)):
        assert not _is_wired(adapters[name]), (
            f"{name} is recorded as out of supported scope with per-model evidence, but "
            "it now implements a forward pass. Either the decision was reversed and the "
            "spec must say so, or something was wired that nothing vouches for."
        )
