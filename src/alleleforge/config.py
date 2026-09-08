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

from pydantic import Field, ValidationError
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
        try:
            return cls(**{**file_kwargs, **overrides})
        except ValidationError as exc:
            # `from None`: this lands in a container log as the entire diagnosis, and
            # the pydantic chain above it is a stack through pydantic-settings that says
            # nothing the message below does not. The field, the value and the reason
            # are all carried across.
            raise ValueError(_settings_problem(exc, env_prefix, path)) from None


def _settings_problem(exc: ValidationError, env_prefix: str, config_file: Path) -> str:
    """Explain a settings validation failure in the operator's own vocabulary.

    Pydantic reports the *field* — "1 validation error for Settings / seed / Input should
    be a valid integer". The operator did not set `seed`; they set `ALLELEFORGE_SEED`, and
    the connection between the two is `env_prefix`, which nothing in the traceback
    mentions. The same name appears in the deployment guide's settings table, so the one
    string a reader could search for is the one string the error does not print.

    It matters more here than in most places because of *where* it lands.
    `alleleforge.web.api.app` builds its app at module scope, so a mistyped variable is
    not a bad request but a container that will not start, and the whole diagnosis is
    whatever this message says. On the command line it was arriving as a traceback and
    exit 1 — the code reserved for a defect in this tool.

    Not softened into a default: a seed or an interval level has no honest degraded mode.
    Substituting the default would stamp every result with a seed the operator did not
    choose, and this project's reproducibility claims rest on that number. Failing to
    start is right; failing to start with a stack trace is not.
    """
    lines = []
    for error in exc.errors():
        field = str(error["loc"][0]) if error["loc"] else "?"
        variable = f"{env_prefix}{field}".upper()
        value = error.get("input")
        lines.append(f"  {variable}={value!r}: {error['msg']}")
    return (
        f"invalid AlleleForge configuration (environment, or {config_file}):\n"
        + "\n".join(lines)
        + "\nEach setting is listed in docs/deployment.md; unset the variable to take the "
        "documented default."
    )


_SETTINGS: Settings | None = None


def get_settings() -> Settings:
    """Return the process-wide :class:`Settings` singleton, loading it once."""
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = Settings.load()
    return _SETTINGS


#: How to authorize an artifact download, in the vocabulary of each surface that can
#: reach the refusal. `consent=True` alone is a Python keyword argument, and the round
#: that unified the three registries left the message speaking only to a Python caller —
#: the same defect the resolver's `DATABASE_REMEDY` exists to avoid, on the other gate.
#: The setting name alone is not enough either: a command-line user has to be told what
#: to actually type.
DOWNLOAD_REMEDY = (
    "pass consent=True from Python, or opt this environment in with "
    "ALLELEFORGE_ALLOW_NETWORK=1 (or allow_network in the config file)"
)


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
