"""Model zoo (Phase 6): license-aware, content-hashed model checkpoints.

Every model AlleleForge wraps carries a required, validated **model card** and is
loaded through the :class:`~alleleforge.model_zoo.registry.ModelRegistry`, which
refuses a missing card, a license that forbids the use, or an unverifiable
checkpoint. Loaded checkpoints surface as Phase 1
:class:`~alleleforge.types.provenance.ModelCheckpoint` records for provenance.
"""

from __future__ import annotations

from alleleforge.model_zoo.registry import (
    CARDS_DIR,
    FORBIDDEN_LICENSES,
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

__all__ = [
    "CARDS_DIR",
    "FORBIDDEN_LICENSES",
    "CardError",
    "ChecksumError",
    "ConsentError",
    "LicenseError",
    "ModelCard",
    "ModelRegistry",
    "ModelUse",
    "default_registry",
    "license_permits",
]
