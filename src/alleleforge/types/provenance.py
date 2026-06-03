"""Provenance blocks: tool, dataset, and model versions for reproducibility.

Every top-level AlleleForge result embeds a :class:`Provenance` block so it can
be re-derived from its inputs. The block records the AlleleForge version, every
wrapped tool/model version and checkpoint hash, every dataset version, the
reference build, the config snapshot, the seed, and a UTC timestamp.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class ToolVersion(BaseModel):
    """The pinned version of a wrapped third-party tool."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    citation: str | None = None
    url: str | None = None


class DatasetVersion(BaseModel):
    """A versioned, license-aware dataset descriptor.

    Attributes:
        name: Dataset identifier (e.g. ``"gnomad"``).
        version: Pinned dataset version (e.g. ``"v4.1"``).
        source_url: Where the dataset is fetched from.
        license: The dataset's license identifier.
        sha256: Content hash of the pinned artifact.
        citation: Literature citation for the dataset.
        redistributable: Whether AlleleForge may vendor this dataset.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    source_url: str | None = None
    license: str | None = None
    sha256: str | None = None
    citation: str | None = None
    redistributable: bool = False


class ModelCheckpoint(BaseModel):
    """A content-hashed model checkpoint with its card metadata.

    Attributes:
        name: Model identifier (e.g. ``"PRIDICT2.0"``).
        version: Model version.
        sha256: Content hash of the checkpoint file.
        chemistry: The chemistry this model scores, if applicable.
        license: The model's license identifier.
        citation: Literature citation for the model.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    sha256: str | None = None
    chemistry: str | None = None
    license: str | None = None
    citation: str | None = None


class Provenance(BaseModel):
    """The reproducibility block embedded in every top-level result.

    Attributes:
        alleleforge_version: The AlleleForge version that produced the result.
        reference_build: The reference genome build used.
        seed: The global random seed in effect.
        tools: Versions of every wrapped tool used.
        datasets: Versions of every dataset accessed.
        models: Checkpoints of every model invoked.
        config_snapshot: A snapshot of the resolved settings.
        timestamp: UTC time the result was produced.
    """

    model_config = ConfigDict(frozen=True)

    alleleforge_version: str
    reference_build: str = "hg38"
    seed: int
    tools: tuple[ToolVersion, ...] = ()
    datasets: tuple[DatasetVersion, ...] = ()
    models: tuple[ModelCheckpoint, ...] = ()
    config_snapshot: dict[str, Any] = {}
    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def _require_utc(cls, value: datetime) -> datetime:
        """Require a timezone-aware UTC timestamp for reproducibility."""
        if value.tzinfo is None:
            raise ValueError("provenance timestamp must be timezone-aware (UTC)")
        return value.astimezone(UTC)

    @classmethod
    def capture(
        cls,
        *,
        alleleforge_version: str,
        seed: int,
        reference_build: str = "hg38",
        timestamp: datetime | None = None,
        **fields: Any,
    ) -> Provenance:
        """Build a provenance block, stamping the current UTC time if needed.

        Args:
            alleleforge_version: The running AlleleForge version.
            seed: The global random seed.
            reference_build: The reference build used.
            timestamp: An explicit timestamp (for reproducible tests); defaults
                to the current UTC time.
            **fields: Any remaining :class:`Provenance` fields (tools, datasets,
                models, config_snapshot).

        Returns:
            A populated :class:`Provenance`.
        """
        return cls(
            alleleforge_version=alleleforge_version,
            seed=seed,
            reference_build=reference_build,
            timestamp=timestamp or datetime.now(UTC),
            **fields,
        )
