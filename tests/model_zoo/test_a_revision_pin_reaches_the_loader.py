"""`source_snapshot` pins the models a single blob hash cannot, and must reach the call.

Three Hugging Face backbones are loaded with `from_pretrained`, which consumes a
*snapshot* — config, tokenizer and weights together — not one file. R695 pinned the
weights blob instead and that was reverted: it made `resolve_weights()` return a cached
`.ckpt` path, so `from_pretrained` was handed a file where it needs a repo id or a
directory, and the real-weights load path broke while the release number improved.
`specs/r0-artifact-pinning.md` has the account.

A revision pin is the right shape for them. What it guarantees and what it does not are
both worth stating, because the difference is why R0's count does not move:

* it does guarantee reproducibility — the bytes behind a 40-hex commit cannot change, so
  two runs naming the same revision load the same model, tokenizer and config;
* it does not give a digest this project computed. The per-blob verification is the hub
  client's, against the metadata upstream published for that revision.

So the pin is only worth anything if it actually reaches the hub call. A revision sitting
in a YAML file that no loader passes along is an audit-trail decoration — the exact
failure mode this project calls honesty theater — and that is what this file prevents.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from alleleforge.model_zoo.registry import ModelCard, SourceSnapshot, default_registry
from alleleforge.scoring.backbone import (
    CaduceusEmbedder,
    Evo2Embedder,
    NucleotideTransformerEmbedder,
    _revision_kwargs,
)

#: The Hugging Face backbones, whose loader takes `from_pretrained` and whose revision
#: this file follows all the way to that call.
_SNAPSHOT_CARDS = ("caduceus", "evo2", "nucleotide-transformer-v2-500m")

#: The checkout adapters, pinned for the same reason but checked at a different seam —
#: `check_checkout_revision` against the directory on disk. Listed here only so the
#: "deliberate edit" assertion below covers every pinned card rather than three of six;
#: their behaviour is pinned in
#: `test_a_pinned_checkout_is_checked_against_the_pin.py`.
_CHECKOUT_SNAPSHOT_CARDS = ("be-dict", "lindel", "pridict2")

_EMBEDDERS = {
    "caduceus": CaduceusEmbedder,
    "evo2": Evo2Embedder,
    "nucleotide-transformer-v2-500m": NucleotideTransformerEmbedder,
}


# -- the pin reaches the call -------------------------------------------------


@pytest.mark.parametrize("name", _SNAPSHOT_CARDS)
def test_a_snapshot_card_hands_the_loader_a_revision(name: str) -> None:
    """The whole point: the sha in the YAML arrives as a `revision=` kwarg.

    Checked through `_revision_kwargs`, which is the mapping `_load` applies, so this
    runs without `transformers` installed. The alternative — asserting the card has a
    revision — would pass just as well if `_load` ignored it entirely.
    """
    embedder = _EMBEDDERS[name](consent=True)
    revision = embedder.snapshot_revision()

    assert revision is not None, f"{name} lost its source_snapshot"
    assert _revision_kwargs(revision) == {"revision": revision}

    card = default_registry().get(name)
    assert revision == card.source_snapshot.revision


@pytest.mark.parametrize("name", _SNAPSHOT_CARDS)
def test_a_snapshot_card_still_loads_by_model_id(name: str) -> None:
    """`resolve_weights()` must stay `None`, or the revision is moot.

    This is the regression that reverted the blob pin. A card pinning
    `checkpoint_sha256` sends `resolve_weights()` down the single-file path and returns a
    local `.ckpt`; `from_pretrained` cannot load that, and `revision=` would be rejected
    beside it. The two pin kinds are mutually exclusive in the schema for this reason,
    and this asserts the consequence rather than the rule.
    """
    embedder = _EMBEDDERS[name](consent=True)
    assert embedder.resolve_weights() is None, (
        f"{name} resolved a local artifact path; `from_pretrained` needs a repo id or a "
        "snapshot directory, so this is the load-breaking state R695 reverted"
    )
    assert _revision_kwargs(None) == {}, "an unpinned load must add no kwargs at all"


@pytest.mark.parametrize("name", _SNAPSHOT_CARDS)
def test_the_pinned_repo_is_the_one_the_embedder_loads(name: str) -> None:
    """The card's repo and the embedder's `model_id` must agree.

    They are written in two files, and nothing else connects them: `_load` passes
    `self.model_id` as the target and the revision from the *card*. If they drifted, the
    loader would ask one repository for a commit that only exists in another — and the
    failure would read as a missing revision rather than as a mismatched card.
    """
    card = default_registry().get(name)
    assert card.source_snapshot.repo == _EMBEDDERS[name].model_id, (
        card.source_snapshot.repo,
        _EMBEDDERS[name].model_id,
    )


# -- the schema refuses what is not a pin -------------------------------------


@pytest.mark.parametrize(
    "revision",
    ["main", "v1.0", "06615c1", "06615C1660C892FC199840C18123F8385B3542A8", "", "x" * 40],
    ids=["branch", "tag", "short-sha", "upper-case", "empty", "not-hex"],
)
def test_a_revision_that_can_move_is_refused(revision: str) -> None:
    """A tag or branch is not a pin, and a short sha is ambiguous.

    Accepting any of them would make the field *look* like a pin while leaving the bytes
    free to change — which is worse than no pin, because a reader stops asking.
    """
    with pytest.raises(ValidationError, match="40-character lower-case commit"):
        SourceSnapshot(repo="owner/name", revision=revision)


@pytest.mark.parametrize(
    "repo",
    ["https://huggingface.co/owner/name", "owner", "owner/name/extra", "/name", "owner/"],
)
def test_a_repo_that_is_not_owner_slash_name_is_refused(repo: str) -> None:
    """A URL does not belong here: the loader that reads this knows its own host."""
    with pytest.raises(ValidationError, match="must be 'owner/name'"):
        SourceSnapshot(repo=repo, revision="a" * 40)


def test_a_card_cannot_carry_both_kinds_of_pin() -> None:
    """Both would mean one is silently ignored, which is the worst of the three states.

    `resolve_weights()` takes the single-file path whenever `checkpoint_sha256` is set
    and never consults the snapshot, so a card with both advertises a revision nothing
    reads. The schema refuses it so the contradiction cannot reach a reviewer as a
    plausible-looking card.
    """
    fields = {
        "name": "x",
        "version": "1",
        "chemistry": None,
        "training_data": "d",
        "intended_use": "u",
        "out_of_scope_use": "o",
        "license": "MIT",
        "citation": "c",
        "known_failure_modes": ("f",),
    }
    with pytest.raises(ValidationError, match="not both"):
        ModelCard(
            **fields,
            checkpoint_sha256="a" * 64,
            source_url="https://example.org/w.bin",
            source_snapshot=SourceSnapshot(repo="owner/name", revision="b" * 40),
        )


def test_a_bundled_card_cannot_carry_a_snapshot() -> None:
    """`bundled` is an availability claim: the code ships, so there is nothing upstream.

    Without this, a weight-free baseline could name a revision and read as though it
    loaded something external.
    """
    with pytest.raises(ValidationError, match="cannot define source_snapshot"):
        ModelCard(
            name="x",
            version="1",
            chemistry=None,
            training_data="d",
            intended_use="u",
            out_of_scope_use="o",
            license="MIT",
            citation="c",
            known_failure_modes=("f",),
            bundled=True,
            source_snapshot=SourceSnapshot(repo="owner/name", revision="b" * 40),
        )


def test_the_snapshot_pinned_set_is_a_deliberate_edit() -> None:
    """Naming the set, so adding a pin means recording where its revision came from.

    A revision is only trustworthy if somebody resolved it against upstream. Pinning one
    by copying a plausible-looking sha is undetectable from inside this repository, so
    the list is kept here and the provenance of each sha in
    `specs/r0-artifact-pinning.md`.
    """
    registry = default_registry()
    pinned = {name for name in registry.names if registry.get(name).source_snapshot is not None}
    assert pinned == set(_SNAPSHOT_CARDS) | set(_CHECKOUT_SNAPSHOT_CARDS), sorted(pinned)
