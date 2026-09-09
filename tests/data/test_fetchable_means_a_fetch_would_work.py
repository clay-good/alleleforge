"""`fetchable` said "both fields a fetch needs are set", not "a fetch would work".

It was `bool(descriptor.sha256 and descriptor.source_url)` — a structural test. For
`doench-2016-cfd` both fields are set and the fetch can never succeed: `source_url` serves
CRISPOR's upstream `mismatch_score.pkl` while `sha256` pins the *vendored JSON conversion*
of it. The shipped file records both digests itself, under `_provenance.sources`, so the
project already knew they differ.

A reader who took `fetchable: True` at its word — fetched the URL, checked it against the
pinned digest — would find a mismatch and reasonably read it as tampering. That reader is
exactly the audience `aforge verify`'s hash contract is built for.

Since the round that made `resolve()` return the bundled bytes, a bundled row has neither
need nor path for a fetch. So the flag now means what its name says, and this file pins it
against *behaviour*: for every registered dataset, `fetchable` must agree with whether
`resolve()` would actually try to download.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alleleforge.data.registry import (
    DEFAULT_REGISTRY,
    ChecksumError,
    ConsentError,
    dataset_status,
)

_BUNDLED = "doench-2016-cfd"


def _names() -> list[str]:
    names = sorted(DEFAULT_REGISTRY.names)
    assert len(names) >= 5, names
    return names


def _would_fetch(name: str, cache_dir: Path) -> bool:
    """Return whether `resolve` reaches the downloader for ``name`` on a cold cache.

    Determined by running it with consent and a downloader that records the attempt
    instead of touching the network.
    """
    attempted: list[str] = []

    def recording(url: str, dest: Path) -> None:
        attempted.append(url)
        raise ChecksumError("stopped before writing; this test never downloads")

    try:
        DEFAULT_REGISTRY.resolve(name, cache_dir=cache_dir, consent=True, downloader=recording)
    except (ChecksumError, ConsentError, OSError):
        pass
    return bool(attempted)


@pytest.mark.parametrize("name", _names())
def test_fetchable_agrees_with_what_resolve_does(name: str, tmp_path: Path) -> None:
    """The flag is a promise about behaviour, so it is checked against behaviour."""
    status = dataset_status(name, DEFAULT_REGISTRY.get(name))
    assert status["fetchable"] == _would_fetch(name, tmp_path / name), (
        f"{name}: status says fetchable={status['fetchable']}, but resolve() "
        f"{'does' if not status['fetchable'] else 'does not'} attempt a download"
    )


def test_the_bundled_row_is_not_advertised_as_fetchable() -> None:
    """Named directly: it is the row the structural test got wrong."""
    descriptor = DEFAULT_REGISTRY.get(_BUNDLED)
    assert descriptor.bundled and descriptor.sha256 and descriptor.source_url
    assert dataset_status(_BUNDLED, descriptor)["fetchable"] is False


def test_the_pinned_digest_is_the_shipped_file_and_not_the_source_url() -> None:
    """The fact behind the flag, read from the shipped file rather than restated.

    If a future vendoring made the two artifacts identical, this fails and the reasoning
    above needs revisiting rather than quietly standing.
    """
    descriptor = DEFAULT_REGISTRY.get(_BUNDLED)
    path = descriptor.bundled_file()
    assert path is not None
    sources = json.loads(path.read_text())["_provenance"]["sources"]
    upstream = {entry["url"]: entry["sha256"] for entry in sources}
    assert descriptor.source_url in upstream, (
        "the row's source_url is not one of the sources the shipped file records"
    )
    assert upstream[descriptor.source_url] != descriptor.sha256, (
        "the upstream artifact and the vendored file now hash the same; the conversion "
        "reasoning in the registry comment needs revisiting"
    )


def test_a_row_with_no_checksum_is_still_not_fetchable() -> None:
    """The guarantee this must not weaken: nothing unverifiable is downloadable."""
    for name in _names():
        descriptor = DEFAULT_REGISTRY.get(name)
        if descriptor.sha256 is None:
            assert dataset_status(name, descriptor)["fetchable"] is False, name
