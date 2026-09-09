"""Seventy-eight percent of a design was re-parsing the same seventeen YAML files.

The comment above `default_registry` said the registry was "populated from the
bundled cards on first use". It was populated on *every* use: seventeen cards read
and parsed per call, and one `design()` calls it six times — through the efficiency,
outcome and prime scorers, and again when the run collects its model checkpoints for
provenance. A profile of a single design put 0.651s of its 0.836s inside
`yaml.safe_load`, over files that ship inside the package and cannot change while
the process runs.

Measured on a 300-variant cohort, same command and inputs, three runs each:

    before   21.28  21.96  20.67  s user CPU
    after     6.91   6.81   7.10  s user CPU

with byte-identical output. A single design goes from ~279ms to ~32ms.

`ModelCard` is frozen, so the parsed cards are shared. `default_registry()` still
returns a *new* `ModelRegistry` around them, so a caller that registers a card into
the object it was handed cannot affect the next caller — the isolation that used to
be an accident of the waste.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.model_zoo import registry as registry_module
from alleleforge.model_zoo.registry import ModelCard, ModelRegistry, default_registry


@pytest.fixture(autouse=True)
def _forget_the_cards() -> None:
    """Each test starts from a cold cache, and leaves one behind for nobody.

    Tolerant of the cache being absent so that removing it fails the check below as an
    assertion about parse counts, rather than erroring every test in this file on a
    missing `cache_clear` — a guard should say what went wrong, not just that it did.
    """
    clear = getattr(registry_module._bundled_cards, "cache_clear", lambda: None)
    clear()
    yield
    clear()


def _count_parses(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Return a one-element list that counts `ModelCard.from_yaml` calls."""
    calls = [0]
    original = ModelCard.from_yaml

    def counting(path: str | Path) -> ModelCard:
        calls[0] += 1
        return original(path)

    monkeypatch.setattr(ModelCard, "from_yaml", staticmethod(counting))
    return calls


def test_the_cards_are_parsed_once_however_often_the_registry_is_asked_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _count_parses(monkeypatch)
    default_registry()
    first = calls[0]
    assert first > 5, f"only {first} card(s) parsed — this check would be vacuous"
    for _ in range(9):
        default_registry()
    assert calls[0] == first, (
        f"{calls[0] - first} extra card parse(s) across ten calls; the bundled cards "
        "are package data and cannot change while the process runs"
    )


def test_every_caller_gets_its_own_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Caching the cards must not start sharing one mutable registry."""
    _count_parses(monkeypatch)
    first, second = default_registry(), default_registry()
    assert first is not second
    borrowed = ModelCard.from_yaml(_any_card()).model_copy(update={"name": "borrowed"})
    first.register(borrowed)
    assert "borrowed" in first
    assert "borrowed" not in second, "one caller's registration reached another's registry"


def test_the_registry_still_holds_the_bundled_cards() -> None:
    """The floor: caching must not hand back an empty registry."""
    names = default_registry().names
    assert len(names) > 5, names
    assert "rule-set-3" in names, names


def test_a_caller_with_their_own_cards_is_not_served_the_bundled_ones(
    tmp_path: Path,
) -> None:
    """`from_cards_dir` with a directory is the path someone takes *because* it differs."""
    card = ModelCard.from_yaml(_any_card())
    (tmp_path / "only.yaml").write_text(
        card.model_copy(update={"name": "only-mine"}).to_yaml()
        if hasattr(card, "to_yaml")
        else _any_card().read_text().replace(card.name, "only-mine", 1),
        encoding="utf-8",
    )
    theirs = ModelRegistry.from_cards_dir(tmp_path)
    assert theirs.names == ("only-mine",), theirs.names


def _any_card() -> Path:
    return sorted(registry_module.CARDS_DIR.glob("*.yaml"))[0]
