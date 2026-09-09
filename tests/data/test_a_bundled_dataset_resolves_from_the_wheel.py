"""`resolve()` could not produce the one dataset that ships inside the package.

`doench-2016-cfd` is the only registry row that is both `bundled` and pinned, and it is
the matrix behind every specificity number the tool prints. `resolve()` went straight to
the cache and never looked at the bundled copy, which gave it two failure modes and no
success mode on a machine that had never fetched:

* **Fresh install, offline.** `ConsentError: dataset 'doench-2016-cfd' is not cached; …
  Source: …/mismatch_score.pkl` — telling a reader to download something the wheel they
  just installed already contains.
* **After any fetch.** The descriptor's `source_url` serves CRISPOR's upstream *pickle*
  while its `sha256` pins the vendored *JSON conversion*, so a fetch writes a `.pkl` under
  the name `cfd_matrix.json` and every later `resolve()` raises `ChecksumError` — for good,
  since the bytes at that URL can never hash to the pinned value. This was found as real
  state on a development machine, not as a hypothesis.

The bytes were correct and present the whole time: the file in `site-packages` hashes to
exactly the pinned digest.

`aforge verify --cache-dir` had already been repaired for this, at its own call site, with
a comment reading "a bundled dataset ships inside the installed package and is never in the
cache". Fixing it there and not in `resolve()` is what left the primary accessor broken —
the same shape as the `pyfaidx` import fixed at the package boundary while ten modules
imported the submodule directly.

Verification is not skipped: the bundled bytes are checksummed against the same pinned
digest. It is a shorter path to the same guarantee, not a way around it.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from alleleforge.data.registry import DEFAULT_REGISTRY, ChecksumError, ConsentError

_BUNDLED = "doench-2016-cfd"


def test_the_row_this_is_about_is_still_bundled_and_pinned() -> None:
    """Both properties are the premise; without either the test proves nothing."""
    descriptor = DEFAULT_REGISTRY.get(_BUNDLED)
    assert descriptor.bundled is True
    assert descriptor.sha256, "the row lost its pinned checksum"
    assert descriptor.bundled_file() is not None


def test_the_bundled_bytes_are_the_pinned_bytes() -> None:
    """The reason resolving to them is safe rather than a shortcut."""
    descriptor = DEFAULT_REGISTRY.get(_BUNDLED)
    path = descriptor.bundled_file()
    assert path is not None and path.is_file()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == descriptor.sha256


def test_a_cold_cache_and_no_consent_still_resolves(tmp_path: Path) -> None:
    """A fresh install, offline: the wheel already has it."""
    path, version = DEFAULT_REGISTRY.resolve(_BUNDLED, cache_dir=tmp_path)
    assert path == DEFAULT_REGISTRY.get(_BUNDLED).bundled_file()
    assert version.name == _BUNDLED
    assert not list(tmp_path.rglob("*")), "resolving a bundled dataset wrote to the cache"


def test_a_cache_holding_the_wrong_bytes_does_not_shadow_the_wheel(tmp_path: Path) -> None:
    """The state this was found in: the upstream pickle, saved under the JSON's name.

    A poisoned cache entry made the dataset permanently unusable on that machine even
    though a verified copy sat in `site-packages`.
    """
    cached = DEFAULT_REGISTRY.cache_path(_BUNDLED, cache_dir=tmp_path)
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(b"(dp0\nS'rU:dT,12'\np1\nF0.8\ns.")  # a pickle, not the JSON
    path, _ = DEFAULT_REGISTRY.resolve(_BUNDLED, cache_dir=tmp_path)
    assert path == DEFAULT_REGISTRY.get(_BUNDLED).bundled_file()


def test_a_dataset_that_is_not_bundled_still_refuses(tmp_path: Path) -> None:
    """The guarantee this must not weaken: no unconsented, unverifiable fetch."""
    with pytest.raises(ConsentError):
        DEFAULT_REGISTRY.resolve("gnomad", cache_dir=tmp_path)


def test_a_bundled_file_that_fails_its_checksum_is_still_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resolving from the wheel is a shorter path to the guarantee, not around it."""
    descriptor = DEFAULT_REGISTRY.get(_BUNDLED)
    tampered = tmp_path / "cfd_matrix.json"
    tampered.write_text("{}")
    monkeypatch.setattr(type(descriptor), "bundled_file", lambda self: tampered)
    with pytest.raises(ChecksumError):
        DEFAULT_REGISTRY.resolve(_BUNDLED, cache_dir=tmp_path)
