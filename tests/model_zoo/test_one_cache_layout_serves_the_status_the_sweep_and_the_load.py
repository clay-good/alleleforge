"""Three surfaces read a checkpoint's cache path; one derivation has to produce it.

``model_status`` reports ``cached``, ``verify_stores`` re-hashes what it finds, and
``WeightGate.resolve_weights`` is the one that actually loads. Each used to spell the
layout for itself -- the sweep built ``root/models/<name>.<version>.ckpt`` by hand,
the loader spelled the ``models`` subdirectory as a literal, and the registry spelled
the filename a second time. Agreement was a coincidence, and the failure it hides is
silent in the worst direction: a checkpoint reported absent, or re-fetched over a copy
already on disk.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from alleleforge import config
from alleleforge.cache_sweep import verify_stores
from alleleforge.model_zoo.loader import WeightGate
from alleleforge.model_zoo.registry import (
    ModelCard,
    ModelRegistry,
    checkpoint_path,
    default_registry,
    model_status,
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
    "known_failure_modes": ("documented demo failure mode",),
}
_BYTES = b"a checkpoint's worth of bytes"


def _plant(card: ModelCard, root: Path) -> Path:
    path = checkpoint_path(card, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_BYTES)
    return path


class _Gated(WeightGate):
    card_name = "demo"


def test_the_load_reads_the_file_status_calls_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no ``cache_dir`` override, the loader resolves the settings cache the same way.

    This is the pairing that matters: ``model_status`` says the checkpoint is available,
    and the loader -- resolving its own default, not handed a path -- returns that very
    file. A layout mismatch makes one of the two wrong with nothing to notice it.
    """
    card = ModelCard(**{**_VALID, "checkpoint_sha256": hashlib.sha256(_BYTES).hexdigest()})  # type: ignore[arg-type]
    planted = _plant(card, tmp_path)
    monkeypatch.setenv("ALLELEFORGE_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(config, "_SETTINGS", None)

    assert model_status(card, tmp_path)["available"] is True

    gate = _Gated(registry=ModelRegistry({"demo": card}), cache_dir=None)
    assert gate.resolve_weights() == str(planted)


def test_the_sweep_hashes_the_file_status_calls_cached(tmp_path: Path) -> None:
    """The sweep must look where ``checkpoint_path`` says, or it checks nothing.

    A pinned card gets bytes that are deliberately *not* its pinned content, so the only
    way the sweep can report a mismatch is by having found the planted file. Reporting it
    missing would be the passing-looking answer if the sweep built its own path.
    """
    registry = default_registry()
    pinned = [n for n in registry.names if registry.get(n).checkpoint_sha256 is not None]
    assert pinned, "no pinned card ships; this check would be vacuous"
    card = registry.get(pinned[0])
    _plant(card, tmp_path)

    checks = {c.artifact: c for c in verify_stores(tmp_path) if c.kind == "checkpoint"}
    found = checks[f"{card.name}.{card.version}"]
    assert found.status == "MISMATCH", f"the sweep did not hash the planted file: {found}"
