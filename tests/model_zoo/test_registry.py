"""Tests for the model-zoo registry: cards, license gate, checkpoint verify."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from alleleforge.model_zoo.registry import (
    CardError,
    ChecksumError,
    ConsentError,
    LicenseError,
    ModelCard,
    ModelRegistry,
    ModelUse,
    default_registry,
    license_permits,
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
}


def _card(**kw: object) -> ModelCard:
    return ModelCard(**{**_VALID, **kw})  # type: ignore[arg-type]


# -- bundled cards ------------------------------------------------------------


def test_default_registry_loads_bundled_cards() -> None:
    reg = default_registry()
    assert "nucleotide-transformer-v2-500m" in reg
    assert "rule-set-3" in reg
    nt = reg.get("nucleotide-transformer-v2-500m")
    assert nt.chemistry is None  # a generic backbone
    assert nt.known_failure_modes  # documented


def test_bundled_card_to_checkpoint() -> None:
    card = default_registry().get("rule-set-3")
    ckpt = card.to_checkpoint()
    assert ckpt.name == "rule-set-3"
    assert ckpt.chemistry == "cas9_nuclease"
    assert ckpt.license == "Apache-2.0"
    # The card's documented failure modes ride into provenance so a result is
    # self-contained for safety audit, not just name/version/license.
    assert ckpt.known_failure_modes == card.known_failure_modes
    assert ckpt.known_failure_modes


# -- card validation ----------------------------------------------------------


def test_missing_card_file_raises(tmp_path: Path) -> None:
    with pytest.raises(CardError, match="not found"):
        ModelCard.from_yaml(tmp_path / "nope.yaml")


def test_non_mapping_card_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("- just\n- a\n- list\n")
    with pytest.raises(CardError, match="not a YAML mapping"):
        ModelCard.from_yaml(bad)


def test_card_missing_required_field_rejected(tmp_path: Path) -> None:
    incomplete = tmp_path / "incomplete.yaml"
    incomplete.write_text("name: x\nversion: '1'\n")  # missing license, intended_use, ...
    with pytest.raises(ValidationError):
        ModelCard.from_yaml(incomplete)


def test_from_yaml_roundtrip(tmp_path: Path) -> None:
    import yaml

    path = tmp_path / "demo.yaml"
    path.write_text(yaml.safe_dump(_VALID))
    card = ModelCard.from_yaml(path)
    assert card.name == "demo" and card.license == "MIT"


# -- license gate -------------------------------------------------------------


def test_license_permits() -> None:
    assert license_permits("MIT", ModelUse.COMMERCIAL)
    assert license_permits("CC-BY-NC-SA-4.0", ModelUse.RESEARCH)
    assert not license_permits("CC-BY-NC-SA-4.0", ModelUse.COMMERCIAL)
    assert not license_permits("proprietary", ModelUse.RESEARCH)


def test_card_permits() -> None:
    assert _card(license="MIT").permits(ModelUse.COMMERCIAL)
    assert not _card(license="research-only").permits(ModelUse.COMMERCIAL)


# -- checkpoint resolution ----------------------------------------------------


def test_checkpoint_unknown_model_raises() -> None:
    with pytest.raises(CardError, match="no model card"):
        ModelRegistry().checkpoint("ghost", cache_dir="/tmp")


def test_checkpoint_license_gate(tmp_path: Path) -> None:
    reg = ModelRegistry({"nc": _card(name="nc", license="CC-BY-NC-4.0")})
    with pytest.raises(LicenseError, match="forbids commercial"):
        reg.checkpoint("nc", cache_dir=tmp_path, use=ModelUse.COMMERCIAL)


def test_checkpoint_requires_consent(tmp_path: Path) -> None:
    reg = ModelRegistry({"demo": _card(checkpoint_sha256="00", source_url="https://x")})
    with pytest.raises(ConsentError, match="consent=True"):
        reg.checkpoint("demo", cache_dir=tmp_path)


def test_checkpoint_requires_pinned_hash(tmp_path: Path) -> None:
    reg = ModelRegistry({"demo": _card(checkpoint_sha256=None, source_url="https://x")})
    with pytest.raises(ChecksumError, match="pins no checkpoint hash"):
        reg.checkpoint("demo", cache_dir=tmp_path, consent=True)


def test_checkpoint_downloads_and_verifies(tmp_path: Path) -> None:
    payload = b"weights"
    digest = hashlib.sha256(payload).hexdigest()
    reg = ModelRegistry({"demo": _card(checkpoint_sha256=digest, source_url="https://x")})

    def fake_dl(url: str, dest: Path) -> None:
        dest.write_bytes(payload)

    path, ckpt = reg.checkpoint("demo", cache_dir=tmp_path, consent=True, downloader=fake_dl)
    assert path.read_bytes() == payload
    assert ckpt.sha256 == digest


def test_checkpoint_detects_corruption(tmp_path: Path) -> None:
    reg = ModelRegistry({"demo": _card(checkpoint_sha256="deadbeef", source_url="https://x")})

    def bad_dl(url: str, dest: Path) -> None:
        dest.write_bytes(b"corrupt")

    with pytest.raises(ChecksumError, match="hash mismatch"):
        reg.checkpoint("demo", cache_dir=tmp_path, consent=True, downloader=bad_dl)


def test_checkpoint_uses_cache(tmp_path: Path) -> None:
    payload = b"w"
    digest = hashlib.sha256(payload).hexdigest()
    reg = ModelRegistry({"demo": _card(checkpoint_sha256=digest, source_url="https://x")})
    calls = {"n": 0}

    def counting_dl(url: str, dest: Path) -> None:
        calls["n"] += 1
        dest.write_bytes(payload)

    reg.checkpoint("demo", cache_dir=tmp_path, consent=True, downloader=counting_dl)
    reg.checkpoint("demo", cache_dir=tmp_path, consent=True, downloader=counting_dl)
    assert calls["n"] == 1


def test_checkpoint_reverifies_cached_file_on_read(tmp_path: Path) -> None:
    # A cached checkpoint is re-hashed on every load: tampering with the file
    # after download is caught, without any new download (consent=False).
    payload = b"weights"
    digest = hashlib.sha256(payload).hexdigest()
    reg = ModelRegistry({"demo": _card(checkpoint_sha256=digest, source_url="https://x")})

    def fake_dl(url: str, dest: Path) -> None:
        dest.write_bytes(payload)

    path, _ = reg.checkpoint("demo", cache_dir=tmp_path, consent=True, downloader=fake_dl)
    path.write_bytes(b"tampered")  # corrupt the cache entry
    with pytest.raises(ChecksumError, match="hash mismatch"):
        reg.checkpoint("demo", cache_dir=tmp_path, consent=False)
