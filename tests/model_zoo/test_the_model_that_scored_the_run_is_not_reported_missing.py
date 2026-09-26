"""A weight-free baseline is bundled, not unavailable.

The five default scorers -- `pridict2-baseline`, `prime-outcome-baseline`,
`be-dict-baseline`, `indelphi-mh-baseline` and `cas9-efficiency-ensemble` -- are
transparent heuristics that ship as code. They have no checkpoint to pin and no source to
fetch from, which from `model_status` looked identical to a trained card that merely forgot
to pin a hash, so all five reported ``NOT AVAILABLE - no pinned checksum, so it can be
neither fetched nor loaded``. Those are the models that produce the numbers in every
default report: `aforge models list` told a reader the scorer behind their menu was missing.

The dataset registry met this first and `dataset_status` has carried `bundled` since, with
`cache_sweep` recording that checking the cache path for packaged bytes "is how a dataset
that is always present came to be reported unavailable once already". This pins the same
distinction on the model side, in both directions -- because a rule that called *every*
checksum-less card available would be the opposite error, and a worse one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.model_zoo.registry import (
    CardError,
    ModelCard,
    default_registry,
    model_presence,
    model_reason,
    model_status,
)

#: The cards that ship as code. Named rather than derived, so adding `bundled: true` to a
#: trained card -- which would announce unverified weights as present -- fails here.
_BUNDLED = (
    "be-dict-baseline",
    "cas9-efficiency-ensemble",
    "indelphi-mh-baseline",
    "pridict2-baseline",
    "prime-outcome-baseline",
)


def _card(name: str) -> ModelCard:
    return default_registry().get(name)


@pytest.mark.parametrize("name", _BUNDLED)
def test_a_bundled_baseline_is_available_with_no_checkpoint(name: str, tmp_path: Path) -> None:
    """Available, with nothing cached and nothing pinned, and its reason says why."""
    card = _card(name)
    assert card.bundled is True
    assert card.checkpoint_sha256 is None and card.source_url is None

    status = model_status(card, tmp_path)
    assert status["available"] is True
    assert status["cached"] is False, "nothing is in this empty cache root"
    assert status["fetchable"] is False, "there is nothing to fetch"
    assert "weight-free baseline" in model_reason(status)
    assert "NOT AVAILABLE" not in model_presence(status)


def test_the_bundled_set_is_exactly_the_cards_without_a_source() -> None:
    """Every bundled card is checksum-less and source-less, and no other card is bundled.

    The second half is the one that matters: `bundled` is a claim that weights are not
    needed, so a trained card carrying it would report unverified weights as present.
    """
    registry = default_registry()
    bundled = {n for n in registry.names if registry.get(n).bundled}
    assert bundled == set(_BUNDLED)
    for name in registry.names:
        card = registry.get(name)
        if card.bundled:
            assert card.checkpoint_sha256 is None, f"{name} claims bundled and pins a hash"
            assert card.source_url is None, f"{name} claims bundled and names a source"


def test_an_unpinned_trained_card_is_still_not_available(tmp_path: Path) -> None:
    """The negative case the fix turns on: no checksum alone does not make a model usable.

    `be-dict` has a source URL and no pinned hash, so the registry refuses to fetch it and
    refuses to load anything found at its cache path. Reporting it like a bundled baseline
    would be the presence-versus-permission confusion pointing the other way.
    """
    card = _card("be-dict")
    assert card.bundled is False
    status = model_status(card, tmp_path)
    assert status["available"] is False
    assert "no pinned checksum" in model_reason(status)
    assert model_presence(status).startswith("NOT AVAILABLE")


def test_asking_a_bundled_model_for_a_checkpoint_says_it_has_none(tmp_path: Path) -> None:
    """Not a consent prompt and not a checksum complaint: there are no weights.

    Either of those answers sends the caller to grant permission, or to pin a hash, for a
    file that does not exist and never will.
    """
    registry = default_registry()
    with pytest.raises(CardError, match="weight-free baseline"):
        registry.checkpoint("prime-outcome-baseline", cache_dir=tmp_path, consent=True)
