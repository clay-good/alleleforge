"""The downloader a real fetch uses is the one no test ever reached.

``checkpoint`` passes ``downloader or _default_downloader`` to ``download_verified``,
and ``download_verified`` takes ``downloader`` as a **required** callable — there is no
second default behind it. Every fetch test in the suite injects a fake, which is right:
CI does not go to the network. But injecting one also means the left side of that ``or``
always won, so nothing established that the production path has a downloader at all.
Drop the fallback and `aforge models fetch`, run by a user who supplies no downloader
because the API does not ask for one, calls ``None(url, dest)``.

The dataset registry writes the identical line and *is* covered, which is what makes
this worth pinning rather than accepting: the two gated fetchers are meant to behave the
same way, and one of them had a hole the other did not.

The network is still never touched — the default is replaced with a recorder, so what is
checked is that the default is *consulted*, not what it does.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from alleleforge.model_zoo import registry as registry_module
from alleleforge.model_zoo.registry import ModelRegistry
from tests.model_zoo.test_registry import _card

_PAYLOAD = b"weights"
_DIGEST = hashlib.sha256(_PAYLOAD).hexdigest()


def test_omitting_a_downloader_uses_the_packages_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def recorder(url: str, dest: Path) -> None:
        calls.append(url)
        dest.write_bytes(_PAYLOAD)

    monkeypatch.setattr(registry_module, "_default_downloader", recorder)
    reg = ModelRegistry(
        {"demo": _card(checkpoint_sha256=_DIGEST, source_url="https://example.invalid/ckpt")}
    )
    path, checkpoint = reg.checkpoint("demo", cache_dir=tmp_path, consent=True)

    assert calls == ["https://example.invalid/ckpt"]
    assert path.read_bytes() == _PAYLOAD
    assert checkpoint.sha256 == _DIGEST


def test_an_injected_downloader_still_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The other side of the `or`, so neither is carrying the test alone."""

    def never(url: str, dest: Path) -> None:  # pragma: no cover - must not run
        raise AssertionError("the default was used although one was supplied")

    def injected(url: str, dest: Path) -> None:
        dest.write_bytes(_PAYLOAD)

    monkeypatch.setattr(registry_module, "_default_downloader", never)
    reg = ModelRegistry(
        {"demo": _card(checkpoint_sha256=_DIGEST, source_url="https://example.invalid/ckpt")}
    )
    path, _ = reg.checkpoint("demo", cache_dir=tmp_path, consent=True, downloader=injected)
    assert path.read_bytes() == _PAYLOAD
