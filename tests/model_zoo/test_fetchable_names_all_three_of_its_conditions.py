"""``fetchable`` is a three-term conjunction; each term is the answer on its own.

``model_status`` is the one derivation four surfaces read -- ``aforge models list``
and ``show``, and the two web model-status responses -- and ``model_reason`` turns
``fetchable`` into the sentence a reader acts on. Its siblings ``pinned``, ``cached``
and ``available`` were pinned by value; ``fetchable`` was only ever asserted to
*exist* as a key, so none of its three terms had a case. Each gets one here, because
each wrong answer is a different lie: that an unpinned model can be fetched, that a
card naming a source names none, or that the copy already on disk still needs
fetching.
"""

from __future__ import annotations

from pathlib import Path

from alleleforge.model_zoo.registry import (
    ModelCard,
    checkpoint_path,
    model_reason,
    model_status,
)

_VALID = {
    "name": "demo",
    "version": "1.0",
    "chemistry": "cas9_nuclease",
    "training_data": "synthetic",
    "intended_use": "research",
    "out_of_scope_use": "clinical",
    "license": "MIT",
    "citation": "Demo et al. 2024",
    "known_failure_modes": ("documented demo failure mode",),
}


def _card(**kw: object) -> ModelCard:
    return ModelCard(**{**_VALID, **kw})  # type: ignore[arg-type]


def _plant(card: ModelCard, root: Path) -> None:
    """Put bytes exactly where ``card``'s checkpoint would be cached."""
    path = checkpoint_path(card, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not a checkpoint")
    assert model_status(card, root)["cached"] is True, "the plant missed the cache path"


def test_pinned_with_a_source_and_nothing_cached_is_the_one_fetchable_state(
    tmp_path: Path,
) -> None:
    """The only state a fetch would help, and the reason says consent is still owed."""
    card = _card(checkpoint_sha256="00" * 32, source_url="https://example.invalid/ckpt")
    status = model_status(card, tmp_path)
    assert status["fetchable"] is True
    assert status["available"] is False, "not cached, so nothing is loadable yet"
    assert model_reason(status) == "fetch it with consent"


def test_an_unpinned_card_is_not_fetchable_however_good_its_url(tmp_path: Path) -> None:
    """The registry refuses to fetch an unpinned checkpoint, so offering one is a lie."""
    card = _card(checkpoint_sha256=None, source_url="https://example.invalid/ckpt")
    status = model_status(card, tmp_path)
    assert status["fetchable"] is False
    assert "no pinned checksum" in model_reason(status)


def test_a_card_naming_no_source_is_not_fetchable(tmp_path: Path) -> None:
    """Pinned and absent is still a dead end when the card names nowhere to look."""
    card = _card(checkpoint_sha256="00" * 32, source_url=None)
    status = model_status(card, tmp_path)
    assert status["fetchable"] is False
    assert status["pinned"] is True, "the refusal must not be the unpinned one"
    assert model_reason(status) == (
        "pinned but not cached, and the card names no source to fetch from"
    )


def test_what_is_already_cached_is_not_fetchable(tmp_path: Path) -> None:
    """A fetch is work to do, not a property of the card: done is not fetchable."""
    card = _card(checkpoint_sha256="00" * 32, source_url="https://example.invalid/ckpt")
    _plant(card, tmp_path)
    status = model_status(card, tmp_path)
    assert status["fetchable"] is False
    assert status["available"] is True
    assert model_reason(status) == "cached and pinned"
