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
#:
#: **A project default, not a published cutoff.** 0.1% is a conventional dividing line
#: between rare and common variation, but nothing makes a variant at 0.09% safe to
#: ignore — it is a scope control, and a rarer allele can still create a PAM in the
#: patient in front of you. Lowering it only ever adds candidate sites; the patient-VCF
#: path exists for the case where frequency is the wrong question entirely.
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

    #: Environment-level opt-in to fetching external **artifacts** — datasets,
    #: model checkpoints, reference genomes. It is the standing form of the
    #: per-call ``consent=True`` flag, for a machine where downloading is already
    #: agreed (a container build, a lab workstation), so a caller does not have to
    #: thread consent through every entry point. Default ``False``: with neither
    #: this nor an explicit ``consent``, nothing is downloaded.
    #:
    #: It does **not** authorize sending anything *out*. A variant sent to a
    #: third-party effect API is a disclosure, not a download, and is gated
    #: separately at its own call site — see
    #: :class:`~alleleforge.variant.effect.VepRestPredictor`.
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


def artifact_download_permitted(consent: bool, *, settings: Settings | None = None) -> bool:
    """Return whether an external *artifact* may be downloaded.

    One predicate for all three registries. The check was written out three times
    identically, and the setting that was supposed to govern it — ``allow_network`` —
    was read by none of them, so an environment that had opted in still had to pass
    ``consent=True`` at every call and an environment that had not could still
    download by passing it.

    Args:
        consent: The caller's explicit per-call opt-in.
        settings: Settings to consult; defaults to the process singleton.

    Returns:
        ``True`` if either the caller consented or the environment has opted in.

    Note:
        This governs downloads only. It never authorizes disclosing user data to a
        third party — that is asked separately at the call site that would do it.
    """
    if consent:
        return True
    return (settings or get_settings()).allow_network
