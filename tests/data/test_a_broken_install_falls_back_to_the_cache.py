"""A bundled dataset whose shipped file is gone is a broken install, not a dead end.

Since `resolve()` learned to return the packaged bytes, it asks two things before using
them — the descriptor *names* a bundled path **and** that path is a file:

    if bundled is not None and bundled.is_file():

Every fixture in the suite exercises the real registry, where the one bundled row's file
is present, so the second arm never decided anything. `dataset_status` writes the same
pair, and `dataset_reason` already has a sentence for the case neither of them was tested
on — "bundled file is missing or failed checksum verification; reinstall AlleleForge" —
which is only reachable through it.

Drop the `is_file()` arm and a partial install (a wheel whose package data did not land,
a file removed by a cleanup, a path that moved between versions) stops being a
degradation and becomes a wall: `resolve()` raises `FileNotFoundError` out of the
checksum read instead of falling through to the cache, and `dataset_status` reports a
*present, verified cache entry* as unavailable. The bytes that would have answered the
question are sitting in the cache directory the whole time.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from alleleforge.data.registry import (
    DEFAULT_REGISTRY,
    DatasetDescriptor,
    DatasetRegistry,
    dataset_reason,
    dataset_status,
)

_PAYLOAD = b'{"probe": 1}\n'
_DIGEST = hashlib.sha256(_PAYLOAD).hexdigest()


def _descriptor(*, bundled_path: str | None) -> DatasetDescriptor:
    return DatasetDescriptor(
        name="probe",
        version="1",
        filename="probe.json",
        license="CC0",
        source_url="https://example.invalid/probe.json",
        sha256=_DIGEST,
        bundled=True,
        bundled_path=bundled_path,
    )


@pytest.fixture
def registry(monkeypatch: pytest.MonkeyPatch) -> DatasetRegistry:
    """A registry holding one bundled row whose shipped file does not exist.

    `dataset_status` derives the cache path from `DEFAULT_REGISTRY` rather than from the
    descriptor it is handed, so the row has to be registered there too for the status
    half of this file to be about the same dataset as the resolve half.
    """
    descriptor = _descriptor(bundled_path="data/__not_installed__.json")
    monkeypatch.setitem(DEFAULT_REGISTRY._descriptors, "probe", descriptor)
    return DatasetRegistry({"probe": descriptor})


def _fill_cache(registry: DatasetRegistry, cache_dir: Path) -> Path:
    path = registry.cache_path("probe", cache_dir=cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_PAYLOAD)
    return path


def test_the_shipped_file_really_is_absent(registry: DatasetRegistry) -> None:
    """The premise. A present file would make every check below vacuous."""
    bundled = registry.get("probe").bundled_file()
    assert bundled is not None and not bundled.is_file()


def test_resolve_falls_through_to_a_valid_cache(registry: DatasetRegistry, tmp_path: Path) -> None:
    cached = _fill_cache(registry, tmp_path)
    path, version = registry.resolve("probe", cache_dir=tmp_path)
    assert path == cached
    assert version.sha256 == _DIGEST


def test_the_status_reports_the_cache_it_can_actually_use(
    registry: DatasetRegistry, tmp_path: Path
) -> None:
    _fill_cache(registry, tmp_path)
    status = dataset_status("probe", registry.get("probe"), cache_dir=tmp_path)
    assert status["cached"] is True
    assert status["verified"] is True
    assert status["available"] is True


def test_with_no_cache_either_the_status_says_so(registry: DatasetRegistry, tmp_path: Path) -> None:
    """The negative case, and the one sentence `dataset_reason` keeps for it."""
    status = dataset_status("probe", registry.get("probe"), cache_dir=tmp_path)
    assert status["available"] is False
    assert "reinstall AlleleForge" in dataset_reason(status)
