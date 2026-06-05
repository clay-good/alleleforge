"""The real backbone resolves weights through the consent-gated model zoo (R1).

These tests exercise the **license + consent + checksum** flow end to end without
torch or the network (an injected downloader), so the safety gate that guards a
real-weights download is verified in CI. The actual tensor load stays behind the
``real_weights`` marker.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from alleleforge.model_zoo.registry import (
    ChecksumError,
    ConsentError,
    LicenseError,
    ModelCard,
    ModelRegistry,
    ModelUse,
)
from alleleforge.scoring.backbone import (
    NucleotideTransformerEmbedder,
    StubEmbedder,
    _HuggingFaceEmbedder,
)
from alleleforge.scoring.cas9_efficiency import EnsembleEfficiencyScorer

_WEIGHTS = b"pretend-checkpoint-bytes"
_WEIGHTS_SHA = hashlib.sha256(_WEIGHTS).hexdigest()


def _pinned_card(sha: str | None = _WEIGHTS_SHA, license_id: str = "MIT") -> ModelCard:
    return ModelCard(
        name="test-backbone",
        version="1.0",
        chemistry=None,
        training_data="synthetic",
        intended_use="testing the consent/download flow",
        out_of_scope_use="anything real",
        license=license_id,
        citation="AlleleForge test suite",
        checkpoint_sha256=sha,
        source_url="https://example.invalid/weights.ckpt",
    )


class _PinnedBackbone(_HuggingFaceEmbedder):
    """A backbone whose card pins a checksummed single artifact."""

    name = "test-backbone"
    card_name = "test-backbone"


# --- the hub-resolved (authorize) path: NT v2 is non-commercial ------------------


def test_nt_backbone_requires_consent() -> None:
    emb = NucleotideTransformerEmbedder()  # bundled card, no pinned hash -> authorize
    with pytest.raises(ConsentError, match="consent"):
        emb.resolve_weights()


def test_nt_backbone_research_consent_records_checkpoint() -> None:
    emb = NucleotideTransformerEmbedder(consent=True)
    target = emb.resolve_weights()
    assert target is None  # no pinned artifact -> load by model id after the gate
    checkpoint = emb.model_checkpoint()
    assert checkpoint is not None
    assert checkpoint.name == "nucleotide-transformer-v2-500m"
    assert checkpoint.license == "CC-BY-NC-SA-4.0"


def test_nt_backbone_blocks_commercial_use() -> None:
    # The default backbone is non-commercial: the license gate refuses it.
    emb = NucleotideTransformerEmbedder(consent=True, use=ModelUse.COMMERCIAL)
    with pytest.raises(LicenseError, match="commercial"):
        emb.resolve_weights()


# --- the pinned-artifact (download + checksum) path -----------------------------


def test_pinned_backbone_downloads_and_verifies(tmp_path: Path) -> None:
    registry = ModelRegistry({"test-backbone": _pinned_card()})
    fetched: list[str] = []

    def downloader(url: str, dest: Path) -> None:
        fetched.append(url)
        dest.write_bytes(_WEIGHTS)

    emb = _PinnedBackbone(
        registry=registry, consent=True, cache_dir=tmp_path, downloader=downloader
    )
    path = emb.resolve_weights()
    assert path is not None and Path(path).read_bytes() == _WEIGHTS
    assert fetched == ["https://example.invalid/weights.ckpt"]
    checkpoint = emb.model_checkpoint()
    assert checkpoint is not None and checkpoint.sha256 == _WEIGHTS_SHA


def test_pinned_backbone_without_consent_refuses(tmp_path: Path) -> None:
    registry = ModelRegistry({"test-backbone": _pinned_card()})
    emb = _PinnedBackbone(registry=registry, cache_dir=tmp_path, downloader=lambda u, d: None)
    with pytest.raises(ConsentError):
        emb.resolve_weights()


def test_pinned_backbone_rejects_corrupt_download(tmp_path: Path) -> None:
    registry = ModelRegistry({"test-backbone": _pinned_card()})

    def bad_downloader(url: str, dest: Path) -> None:
        dest.write_bytes(b"corrupted")

    emb = _PinnedBackbone(
        registry=registry, consent=True, cache_dir=tmp_path, downloader=bad_downloader
    )
    with pytest.raises(ChecksumError):
        emb.resolve_weights()


# --- chemistry wiring: the cas9 scorer surfaces the backbone checkpoint ----------


def test_cas9_scorer_backbone_checkpoint_is_none_for_stub() -> None:
    scorer = EnsembleEfficiencyScorer(embedder=StubEmbedder(dim=8))
    assert scorer.backbone_checkpoint() is None


def test_cas9_scorer_surfaces_resolved_backbone_checkpoint(tmp_path: Path) -> None:
    registry = ModelRegistry({"test-backbone": _pinned_card()})
    emb = _PinnedBackbone(
        registry=registry,
        consent=True,
        cache_dir=tmp_path,
        downloader=lambda u, d: d.write_bytes(_WEIGHTS),
    )
    emb.resolve_weights()  # consent-gated resolution records the checkpoint
    scorer = EnsembleEfficiencyScorer(embedder=emb)
    checkpoint = scorer.backbone_checkpoint()
    assert checkpoint is not None and checkpoint.sha256 == _WEIGHTS_SHA
