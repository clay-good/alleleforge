"""A pinned checkpoint hash is only a pin if the URL beside it cannot change.

`ensure_checkpoint` fetches `card.source_url` as a single file and verifies it against
`card.checkpoint_sha256`, then re-hashes on every later read. That machinery is sound,
and it is only as good as the pairing: **a hash pinned next to a mutable address is not a
pin, it is a time bomb.** If `source_url` names a branch, a model landing page, or a
directory, then the bytes behind it change whenever upstream pushes, and the next fetch
fails the checksum — the consent gate then refuses the model outright, so a user who
could previously load it cannot, and the error says "hash mismatch" rather than "upstream
moved".

That is the failure this file prevents, and it is newly possible: before R695 exactly one
card pinned a hash, so the pairing could not be got wrong at scale. Three more now pin
one, and the rule needs to be stated before the fourth.

The converse is deliberately *not* asserted. An unpinned card may name a page, and most
do — eight of them name a repository, which is the honest thing to publish when upstream
has frozen no single artifact. Requiring immutability there would force a fake pin.

Also guards two URLs that were found dead (HTTP 404) while pinning R0: a card citing an
address that does not resolve is worse than one that is merely unpinned, because the
claim looks checkable and is not. Liveness itself needs the network and CI is offline, so
what is pinned here is the narrower, durable fact: those two owners are wrong and must
not come back.
"""

from __future__ import annotations

import re

import pytest

from alleleforge.model_zoo.registry import default_registry

#: A Hugging Face URL is immutable only at a 40-hex commit revision:
#: `/resolve/<sha>/<file>`. A `/resolve/main/...` or a bare model page is not.
_HF_IMMUTABLE = re.compile(r"^https://huggingface\.co/[^/]+/[^/]+/resolve/[0-9a-f]{40}/.+$")

#: A GitHub URL is immutable at a commit sha or a release asset, never at a branch.
_GH_IMMUTABLE = re.compile(
    r"^https://(raw\.githubusercontent\.com/[^/]+/[^/]+/[0-9a-f]{40}/.+"
    r"|github\.com/[^/]+/[^/]+/releases/download/[^/]+/.+)$"
)

#: Owners whose repositories 404'd when the model cards were audited. Replacements are
#: recorded in the cards themselves; these must not reappear.
_DEAD_OWNERS = {
    "Liam-Chen": "github.com/Liam-Chen/PRIDICT2 404'd; PRIDICT2 is at uzh-dqbm-cmi/PRIDICT2",
    "AhmedjBaqer": "github.com/AhmedjBaqer/X-CRISP 404'd; X-CRISP is at joanagoncalveslab/XCRISP",
}


def _cards() -> list:
    registry = default_registry()
    return [registry.get(name) for name in registry.names]


def test_the_registry_is_not_empty() -> None:
    """The premise: every assertion below is vacuous over an empty registry."""
    assert len(_cards()) >= 12


@pytest.mark.parametrize("card", _cards(), ids=lambda c: c.name)
def test_a_card_that_pins_a_hash_pins_an_immutable_url(card: object) -> None:
    """The invariant. A hash without an immutable URL breaks on upstream's next push.

    Deliberately checks the *pair*, not either field alone: the registry already
    refuses to fetch without a hash and refuses to load a cached artifact without one,
    so the gap this closes is the one neither of those can see — a hash that verifies
    today against an address that will serve different bytes tomorrow.
    """
    sha = getattr(card, "checkpoint_sha256", None)
    if sha is None:
        pytest.skip("unpinned: naming a page is honest when upstream froze no artifact")

    url = getattr(card, "source_url", None)
    assert url is not None, (
        f"{card.name} pins a hash with no source_url; the hash can never be checked"
    )
    assert _HF_IMMUTABLE.match(url) or _GH_IMMUTABLE.match(url), (
        f"{card.name} pins checkpoint_sha256 but its source_url is not immutable:\n"
        f"  {url}\n"
        "A hash beside a branch, a landing page or a directory fails the moment upstream "
        "pushes, and the consent gate then refuses the model with 'hash mismatch' rather "
        "than 'upstream moved'. Pin the URL to a commit revision or a release asset."
    )


@pytest.mark.parametrize("card", _cards(), ids=lambda c: c.name)
def test_no_card_cites_a_url_that_was_found_dead(card: object) -> None:
    """Regression guard for two 404s found while pinning R0.

    Liveness cannot be asserted offline, so this pins the durable half: the specific
    owners that were wrong. A reader who reintroduces one gets the replacement in the
    failure message rather than having to re-run the search.
    """
    url = getattr(card, "source_url", None) or ""
    for owner, why in _DEAD_OWNERS.items():
        assert f"/{owner}/" not in url, (card.name, why)


@pytest.mark.parametrize("card", _cards(), ids=lambda c: c.name)
def test_a_source_url_is_a_plain_https_address(card: object) -> None:
    """No `http://`, no credentials, no fragment: these are fetched unattended.

    `ensure_checkpoint` hands this straight to a downloader, so a `http://` URL would
    fetch model weights over plaintext and an embedded credential would be published in
    the repository.
    """
    url = getattr(card, "source_url", None)
    if url is None:
        pytest.skip("no source_url")
    assert url.startswith("https://"), (card.name, url)
    assert "@" not in url.split("//", 1)[1].split("/", 1)[0], (
        f"{card.name}'s source_url carries credentials in its host",
        url,
    )
    assert "#" not in url, (card.name, url)


def test_every_pinned_hash_is_a_full_sha256() -> None:
    """A truncated or upper-case digest would never match `hashlib`'s output.

    `_verify_sha256` compares against `hexdigest()`, which is 64 lower-case hex
    characters. A digest pasted at the wrong length fails every fetch, and the failure
    reads as upstream tampering rather than as a typo in this repository.
    """
    for card in _cards():
        sha = getattr(card, "checkpoint_sha256", None)
        if sha is None:
            continue
        assert re.fullmatch(r"[0-9a-f]{64}", sha), (card.name, sha)


def test_the_cards_that_pin_a_hash_are_the_ones_expected() -> None:
    """Names the pinned set, so adding a pin is a deliberate edit to this list.

    Not a style rule: pinning a hash changes a model from "cannot be fetched" to "will
    be fetched and verified", which is a release-criteria-moving claim (R0). It should
    not happen as a side effect of editing a card for some other reason.
    """
    pinned = {c.name for c in _cards() if getattr(c, "checkpoint_sha256", None) is not None}
    assert pinned == {"rule-set-3"}, (
        "the set of hash-pinned cards changed; `specs/r0-artifact-pinning.md` explains "
        "why the Hugging Face backbones must NOT be pinned per-blob — their loader calls "
        "`from_pretrained(target)`, which needs a snapshot directory, not one file",
        sorted(pinned),
    )
