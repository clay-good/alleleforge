"""Global configuration and defaults for AlleleForge.

Every cross-cutting default from the specification lives here as a typed,
overridable field on :class:`Settings`. Settings are resolved in this order
(later wins): field defaults -> ``~/.config/alleleforge/config.toml`` ->
``ALLELEFORGE_*`` environment variables -> explicit constructor arguments.

Nothing in this module imports CRISPR logic; it is pure infrastructure.
"""

from __future__ import annotations

import os
import random
import tomllib
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Global random seed, threaded through every stochastic step and recorded in
#: provenance. Chosen once in the spec (2024-05-01) so results are re-derivable.
DEFAULT_SEED = 20240501

#: Default reference genome build. T2T-CHM13 is auto-recommended by the genome
#: layer for hg38-ambiguous loci, but hg38 is the baseline everywhere.
DEFAULT_REFERENCE = "hg38"

#: Default predictive-interval level for the uncertainty contract (Phase 1).
DEFAULT_INTERVAL_LEVEL = 0.80

#: Default population minor-allele-frequency threshold for off-target inclusion.
DEFAULT_MAF_THRESHOLD = 0.001


def _default_cache_dir() -> Path:
    """Return the XDG-compliant cache root for AlleleForge.

    Honors ``$XDG_CACHE_HOME`` and falls back to ``~/.cache/alleleforge``.
    """
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "alleleforge"


def _default_config_file() -> Path:
    """Return the path to the user config TOML (``~/.config/alleleforge``)."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "alleleforge" / "config.toml"


class Settings(BaseSettings):
    """Typed, overridable global settings.

    Read fields off a singleton via :func:`get_settings`, or construct an
    instance directly in tests to pin behavior without touching the
    environment.
    """

    model_config = SettingsConfigDict(
        env_prefix="ALLELEFORGE_",
        env_file=None,
        extra="ignore",
        frozen=True,
    )

    cache_dir: Path = Field(default_factory=_default_cache_dir)
    seed: int = DEFAULT_SEED
    reference: str = DEFAULT_REFERENCE
    interval_level: float = Field(default=DEFAULT_INTERVAL_LEVEL, ge=0.0, le=1.0)
    maf_threshold: float = Field(default=DEFAULT_MAF_THRESHOLD, ge=0.0, le=1.0)

    #: When false, the data/model registries must never auto-download; callers
    #: pass an explicit consent flag to fetch external artifacts.
    allow_network: bool = False

    def rng(self) -> random.Random:
        """Return the single run-scoped RNG, seeded from :attr:`seed`.

        Every stochastic step in a run SHALL draw from this one generator so the
        recorded :attr:`seed` is *load-bearing*: change the seed and any randomness
        changes; fix it and the run reproduces byte-for-byte. Construct it once per
        run and thread the same instance through the stochastic steps — do not call
        :func:`random.random` or seed an ad-hoc generator, which would make the
        provenance seed decorative. A fresh instance is returned on each call, so
        the caller owns draw order.
        """
        return random.Random(self.seed)

    def snapshot(self) -> dict[str, Any]:
        """Return the resolved settings for provenance, minus volatile paths.

        The full resolved settings are recorded in a result's provenance so the run
        is re-derivable from what actually governed it, rather than a hand-built
        subset that can drift. The per-machine ``cache_dir`` is dropped because it
        is a local filesystem path, not part of the reproducible result.
        """
        data: dict[str, Any] = self.model_dump(mode="json")
        data.pop("cache_dir", None)
        return data

    @classmethod
    def load(cls, config_file: Path | None = None, **overrides: Any) -> Settings:
        """Build settings from the user TOML, environment, then overrides.

        Args:
            config_file: Path to a TOML file; defaults to the XDG config path.
                Missing files are ignored.
            **overrides: Explicit field overrides (highest precedence).

        Returns:
            A frozen :class:`Settings` instance.
        """
        path = config_file or _default_config_file()
        file_values: dict[str, Any] = {}
        if path.is_file():
            with path.open("rb") as fh:
                file_values = tomllib.load(fh)
        # Documented precedence is defaults < file < env < overrides. Passing a
        # file value as an init kwarg would place it *above* the environment (init
        # kwargs outrank env sources in pydantic-settings), inverting "env
        # overrides file". So a file value yields to an explicit override and to a
        # matching ``ALLELEFORGE_*`` env var; BaseSettings then reads the env for
        # those fields itself, leaving env > file > defaults intact.
        env_prefix = str(cls.model_config.get("env_prefix", ""))
        env_set = {k.upper() for k in os.environ}
        file_kwargs = {
            key: value
            for key, value in file_values.items()
            if key not in overrides and f"{env_prefix}{key}".upper() not in env_set
        }
        return cls(**{**file_kwargs, **overrides})


_SETTINGS: Settings | None = None


def get_settings() -> Settings:
    """Return the process-wide :class:`Settings` singleton, loading it once."""
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = Settings.load()
    return _SETTINGS
