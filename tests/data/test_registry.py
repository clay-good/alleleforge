"""Tests for the consent-gated, checksum-enforcing dataset registry."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from alleleforge.data.registry import (
    DEFAULT_REGISTRY,
    ChecksumError,
    ConsentError,
    DatasetDescriptor,
    DatasetRegistry,
)


def _descriptor(**kw: object) -> DatasetDescriptor:
    base = {
        "name": "demo",
        "version": "1.0",
        "source_url": "https://example.org/demo.tsv",
        "license": "CC0-1.0",
        "citation": "Demo et al. 2024",
        "redistributable": True,
        "filename": "demo.tsv",
    }
    base.update(kw)
    return DatasetDescriptor(**base)  # type: ignore[arg-type]


def test_default_registry_lists_all_phase3_datasets() -> None:
    assert DEFAULT_REGISTRY.names == (
        "1000g",
        "clinvar",
        "dbsnp",
        "encode",
        "gencode",
        "gnomad",
        "hgdp",
    )


def test_every_default_descriptor_has_license_and_citation() -> None:
    for name in DEFAULT_REGISTRY.names:
        desc = DEFAULT_REGISTRY.get(name)
        assert desc.license, name
        assert desc.citation, name
        assert desc.source_url, name


def test_get_unknown_raises_keyerror() -> None:
    with pytest.raises(KeyError, match="unknown dataset"):
        DatasetRegistry().get("nope")


def test_contains_and_register() -> None:
    reg = DatasetRegistry()
    assert "demo" not in reg
    reg.register(_descriptor())
    assert "demo" in reg
    assert reg.names == ("demo",)


def test_resolve_without_consent_raises(tmp_path: Path) -> None:
    reg = DatasetRegistry({"demo": _descriptor(sha256="00")})
    with pytest.raises(ConsentError, match="consent=True"):
        reg.resolve("demo", cache_dir=tmp_path)


def test_resolve_without_checksum_refuses(tmp_path: Path) -> None:
    reg = DatasetRegistry({"demo": _descriptor(sha256=None)})
    with pytest.raises(ChecksumError, match="no pinned checksum"):
        reg.resolve("demo", cache_dir=tmp_path, consent=True)


def test_resolve_downloads_and_verifies(tmp_path: Path) -> None:
    payload = b"chrom\tpos\n"
    digest = hashlib.sha256(payload).hexdigest()
    reg = DatasetRegistry({"demo": _descriptor(sha256=digest)})

    def fake_download(url: str, dest: Path) -> None:
        dest.write_bytes(payload)

    path, version = reg.resolve("demo", cache_dir=tmp_path, consent=True, downloader=fake_download)
    assert path.read_bytes() == payload
    assert version.name == "demo"
    assert version.sha256 == digest


def test_resolve_detects_corruption(tmp_path: Path) -> None:
    reg = DatasetRegistry({"demo": _descriptor(sha256="deadbeef")})

    def corrupt_download(url: str, dest: Path) -> None:
        dest.write_bytes(b"unexpected")

    with pytest.raises(ChecksumError, match="checksum mismatch"):
        reg.resolve("demo", cache_dir=tmp_path, consent=True, downloader=corrupt_download)


def test_resolve_uses_cache_on_second_call(tmp_path: Path) -> None:
    payload = b"data"
    digest = hashlib.sha256(payload).hexdigest()
    reg = DatasetRegistry({"demo": _descriptor(sha256=digest)})
    calls = {"n": 0}

    def counting_download(url: str, dest: Path) -> None:
        calls["n"] += 1
        dest.write_bytes(payload)

    reg.resolve("demo", cache_dir=tmp_path, consent=True, downloader=counting_download)
    reg.resolve("demo", cache_dir=tmp_path, consent=True, downloader=counting_download)
    assert calls["n"] == 1  # second call served from cache


def test_resolve_reverifies_cached_artifact_on_read(tmp_path: Path) -> None:
    # A cached dataset is re-hashed on resolve: a tampered cache entry is rejected
    # on load, with no new download (consent=False).
    payload = b"data"
    digest = hashlib.sha256(payload).hexdigest()
    reg = DatasetRegistry({"demo": _descriptor(sha256=digest)})

    def fake_download(url: str, dest: Path) -> None:
        dest.write_bytes(payload)

    path, _ = reg.resolve("demo", cache_dir=tmp_path, consent=True, downloader=fake_download)
    path.write_bytes(b"tampered")
    with pytest.raises(ChecksumError, match="checksum mismatch"):
        reg.resolve("demo", cache_dir=tmp_path, consent=False)


def test_descriptor_dataset_version_roundtrips() -> None:
    desc = _descriptor(populations=("afr", "eas"))
    version = desc.dataset_version()
    assert version.name == "demo"
    assert version.redistributable is True
    assert not hasattr(version, "filename")
