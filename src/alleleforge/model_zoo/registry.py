"""Model zoo: license-aware, content-hashed model checkpoints with cards.

Every model AlleleForge wraps carries a required **model card** — a YAML file
declaring its name, version, chemistry, training data, metrics, intended and
out-of-scope use, license, citation, known failure modes, and the expected
checkpoint hash. The :class:`ModelRegistry` is the single choke point for loading
a checkpoint, and it enforces:

* **A card is mandatory.** Loading a checkpoint with no card, or a card missing a
  required field, fails loudly (a model with no documented intended use and
  license has no business running).
* **The license must permit the use.** A non-commercial card cannot be loaded for
  commercial use; a forbidden/unknown license is refused outright. The default
  use is ``research``.
* **The checkpoint must verify.** A pinned ``checkpoint_sha256`` is required to
  fetch, and the downloaded bytes are checksum-verified.

Each loaded checkpoint is surfaced as a Phase 1
:class:`~alleleforge.types.provenance.ModelCheckpoint` for the result provenance
block. Card parsing needs no ML dependency, so the registry is testable in CI
without any real weights.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from functools import cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

from alleleforge._fetch import download_verified
from alleleforge.config import DOWNLOAD_REMEDY, artifact_download_permitted
from alleleforge.errors import ChecksumError, ConsentError, MissingDependencyError
from alleleforge.types.provenance import ModelCheckpoint

# Re-exported (the `as` form is the explicit one) so every caller keeps reading the
# licence-gate enum from the model zoo: it is defined one layer down only because
# `alleleforge.config` — which the registry itself imports — needs it for
# `Settings.model_use`.
from alleleforge.types.provenance import ModelUse as ModelUse

#: Directory of bundled model cards shipped with AlleleForge.
CARDS_DIR = Path(__file__).parent / "cards"

#: A downloader writes the artifact at ``url`` to ``dest`` (injected for tests).
Downloader = Callable[[str, Path], None]

#: Licenses AlleleForge refuses to load under any use (no redistribution / unknown).
FORBIDDEN_LICENSES = frozenset({"proprietary", "none", "unknown", "all-rights-reserved"})

#: Substrings marking a non-commercial license (blocks commercial use).
_NONCOMMERCIAL_MARKERS = ("-nc", "noncommercial", "non-commercial", "research-only")


class LicenseError(RuntimeError):
    """Raised when a card's license forbids the requested use."""


class CardError(RuntimeError):
    """Raised when a model card is missing or malformed."""


def license_permits(license_id: str, use: ModelUse) -> bool:
    """Return ``True`` if ``license_id`` permits ``use``.

    A forbidden/unknown license is never permitted; a non-commercial license is
    permitted for research but not commercial use.
    """
    norm = license_id.strip().lower()
    if norm in FORBIDDEN_LICENSES:
        return False
    if use is ModelUse.COMMERCIAL and any(m in norm for m in _NONCOMMERCIAL_MARKERS):
        return False
    return True


class ModelCard(BaseModel):
    """A required, validated model card (mirrors ``cards/*.yaml``).

    Attributes:
        name: Model identifier.
        version: Model version.
        chemistry: The chemistry it scores, or ``None`` for a generic backbone.
        training_data: A description of the training data.
        metrics: Reported metrics (name -> value).
        intended_use: What the model is for.
        out_of_scope_use: What it must not be used for.
        license: SPDX-style license identifier.
        citation: Literature citation.
        known_failure_modes: Documented ways the model fails.
        checkpoint_sha256: Expected checkpoint hash (``None`` blocks download).
        source_url: Where the checkpoint is fetched from.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    chemistry: str | None
    training_data: str
    metrics: dict[str, float] = {}
    intended_use: str
    out_of_scope_use: str
    license: str
    citation: str
    known_failure_modes: tuple[str, ...]
    checkpoint_sha256: str | None = None
    source_url: str | None = None

    @field_validator("known_failure_modes")
    @classmethod
    def _require_failure_modes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Require at least one documented failure mode.

        A model's audit surface is incomplete without its known failure modes, so
        every card SHALL name at least one — a result carries these into provenance
        (:meth:`to_checkpoint`) precisely so a consumer can check a design against
        what the models are known to get wrong.
        """
        if not value:
            raise ValueError("a model card must document at least one known_failure_mode")
        return value

    @classmethod
    def from_yaml(cls, path: str | Path) -> ModelCard:
        """Load and validate a model card from a YAML file.

        Raises:
            CardError: If the file is missing or is not a YAML mapping.
        """
        p = Path(path)
        if not p.is_file():
            raise CardError(f"model card not found: {p}")
        data = yaml.safe_load(p.read_text())
        if not isinstance(data, dict):
            raise CardError(f"model card {p} is not a YAML mapping")
        return cls.model_validate(data)

    def permits(self, use: ModelUse) -> bool:
        """Return ``True`` if this card's license permits ``use``."""
        return license_permits(self.license, use)

    def to_checkpoint(self) -> ModelCheckpoint:
        """Return the Phase 1 :class:`ModelCheckpoint` for provenance."""
        return ModelCheckpoint(
            name=self.name,
            version=self.version,
            sha256=self.checkpoint_sha256,
            chemistry=self.chemistry,
            license=self.license,
            citation=self.citation,
            # The card's three honesty fields travel together or the audit trail is
            # partial: what it is for, what it must not be used for, and how it fails.
            # Only the last one used to make the trip.
            intended_use=self.intended_use,
            out_of_scope_use=self.out_of_scope_use,
            known_failure_modes=self.known_failure_modes,
        )


def _verify_sha256(path: Path, expected: str) -> str:
    """Hash ``path`` and raise :class:`ChecksumError` on mismatch."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    digest = h.hexdigest()
    if digest != expected:
        raise ChecksumError(f"checkpoint hash mismatch for {path}: {digest} != {expected}")
    return digest


def _default_downloader(url: str, dest: Path) -> None:  # pragma: no cover - network
    """Fetch ``url`` to ``dest`` over the network (never exercised in CI)."""
    import urllib.request

    urllib.request.urlretrieve(url, dest)  # noqa: S310 - URLs come from a trusted card


class ModelRegistry:
    """A keyed collection of :class:`ModelCard` with gated checkpoint loading."""

    def __init__(self, cards: dict[str, ModelCard] | None = None) -> None:
        """Initialise the registry, optionally seeding it with cards."""
        self._cards: dict[str, ModelCard] = dict(cards or {})

    def register(self, card: ModelCard) -> None:
        """Add or replace a card keyed by its model name."""
        self._cards[card.name] = card

    def __contains__(self, name: str) -> bool:
        """Return ``True`` if a card named ``name`` is registered."""
        return name in self._cards

    @property
    def names(self) -> tuple[str, ...]:
        """Return the registered model names, sorted."""
        return tuple(sorted(self._cards))

    def get(self, name: str) -> ModelCard:
        """Return the card named ``name``.

        Raises:
            CardError: If no card by that name is registered.
        """
        if name not in self._cards:
            raise CardError(f"no model card registered for {name!r}; known: {self.names}")
        return self._cards[name]

    @classmethod
    def from_cards_dir(cls, cards_dir: str | Path = CARDS_DIR) -> ModelRegistry:
        """Build a registry from every ``*.yaml`` card in ``cards_dir``."""
        registry = cls()
        for path in sorted(Path(cards_dir).glob("*.yaml")):
            registry.register(ModelCard.from_yaml(path))
        return registry

    def checkpoint(
        self,
        name: str,
        *,
        cache_dir: str | Path,
        use: ModelUse = ModelUse.RESEARCH,
        consent: bool = False,
        downloader: Downloader | None = None,
    ) -> tuple[Path, ModelCheckpoint]:
        """Resolve a checkpoint to a verified local path and provenance record.

        Args:
            name: The registered model name.
            cache_dir: Where to cache the downloaded checkpoint.
            use: The use the checkpoint is loaded for (license gate).
            consent: Must be ``True`` to permit a network download.
            downloader: Injected fetcher; defaults to a network download.

        Returns:
            ``(checkpoint_path, ModelCheckpoint)``.

        Raises:
            CardError: If the model has no card.
            LicenseError: If the license forbids ``use``.
            ConsentError: If a download is required but ``consent`` is ``False``.
            ChecksumError: If the card pins no hash, or verification fails.
        """
        card = self.get(name)
        if not card.permits(use):
            raise LicenseError(
                f"license {card.license!r} forbids {use.value} use of model {name!r}"
            )
        path = Path(cache_dir) / f"{card.name}.{card.version}.ckpt"
        if not path.exists():
            if not artifact_download_permitted(consent):
                raise ConsentError(
                    f"checkpoint for {name!r} is not cached; {DOWNLOAD_REMEDY}. "
                    f"Source: {card.source_url}"
                )
            if card.checkpoint_sha256 is None:
                raise ChecksumError(
                    f"model {name!r} pins no checkpoint hash; refusing to fetch an unverifiable "
                    "artifact"
                )
            if card.source_url is None:
                # Not a ConsentError: consent was already given — this code is past the
                # permission check — and the caller who reads "consent" and supplies it
                # again gets the same refusal. What is missing is a place to fetch from.
                raise MissingDependencyError(
                    f"model {name!r} pins no source_url, so its checkpoint cannot be "
                    "fetched; supply the file in the cache directory instead"
                )
            download_verified(
                card.source_url,
                path,
                downloader=downloader or _default_downloader,
                verify=lambda tmp: _verify_sha256(tmp, str(card.checkpoint_sha256)),
            )
        elif card.checkpoint_sha256 is None:
            # A cached but *unpinned* checkpoint must fail closed exactly like the
            # download path (which refuses to fetch an unverifiable artifact) — an
            # out-of-band file dropped at the cache path for an unpinned card would
            # otherwise load unverified, bypassing the "a pinned hash is required to
            # load" guarantee. Only the pinned+cached case is trusted (after re-hash).
            raise ChecksumError(
                f"model {name!r} pins no checkpoint hash; refusing to load an unverifiable "
                "cached artifact"
            )
        else:
            # Hash-on-read: a cached checkpoint is re-verified against its pinned
            # hash on every load, not only when first downloaded, so a tampered or
            # truncated cache entry fails closed rather than being trusted silently.
            _verify_sha256(path, card.checkpoint_sha256)
        return path, card.to_checkpoint()

    def authorize(
        self,
        name: str,
        *,
        use: ModelUse = ModelUse.RESEARCH,
        consent: bool = False,
    ) -> ModelCheckpoint:
        """Run the license + consent gate for a hub-resolved model.

        Some backbones (e.g. HuggingFace transformers) are fetched by their own
        integrity-checked loader rather than as a single pinned artifact, so the
        full :meth:`checkpoint` download/checksum step does not apply. This is the
        lighter gate they share: it enforces the license for the requested use and
        requires explicit consent before any (loader-driven) download, and returns
        the provenance :class:`ModelCheckpoint` to stamp into the result.

        Args:
            name: The registered model name.
            use: The use the model is loaded for (license gate).
            consent: Must be ``True`` to authorize a download.

        Returns:
            The card's :class:`ModelCheckpoint` for the provenance block.

        Raises:
            CardError: If the model has no card.
            LicenseError: If the license forbids ``use``.
            ConsentError: If ``consent`` is ``False``.
        """
        card = self.get(name)
        if not card.permits(use):
            raise LicenseError(
                f"license {card.license!r} forbids {use.value} use of model {name!r}"
            )
        # `artifact_download_permitted`, not a bare `consent` check. The round that
        # introduced that predicate says why in its docstring — "the setting that was
        # supposed to govern it, allow_network, was read by none of them" — and unified
        # three registries. This fourth gate is in the same file as one of them, sixty
        # lines away, and kept its own check: an environment that had opted in got
        # weights for a pinned-artifact model and was refused for a loader-driven one.
        if not artifact_download_permitted(consent):
            raise ConsentError(
                f"loading model {name!r} downloads weights from {card.source_url}; "
                f"{DOWNLOAD_REMEDY}"
            )
        return card.to_checkpoint()


@cache
def _bundled_cards() -> tuple[ModelCard, ...]:
    """Parse the bundled model cards once, and hold them.

    The comment that used to sit above :func:`default_registry` said the registry was
    "populated from the bundled cards on first use". It was populated on *every* use:
    seventeen YAML files read and parsed per call, and a single `design()` calls it six
    times — through the efficiency, outcome and prime scorers, and again when the run
    collects its model checkpoints for provenance. Profiling one design put **78% of its
    wall clock in `yaml.safe_load`** over static files that ship inside the package and
    cannot change while the process runs. A three-hundred-variant cohort spent minutes
    re-reading the same seventeen files.

    `ModelCard` is frozen, so the parsed cards are safe to share; `default_registry`
    still returns a fresh :class:`ModelRegistry` around them, so a caller that registers
    a card into the object it was handed cannot affect the next caller — the isolation
    that was previously a side effect of the waste.

    :meth:`ModelRegistry.from_cards_dir` with an explicit directory stays uncached: it
    is the path a caller uses precisely because they have their own cards.
    """
    return tuple(ModelCard.from_yaml(path) for path in sorted(CARDS_DIR.glob("*.yaml")))


def default_registry() -> ModelRegistry:
    """Return a registry built from the bundled model cards.

    The cards are read once per process (:func:`_bundled_cards`); the registry object
    is new each call, so it is the caller's to mutate.
    """
    return ModelRegistry({card.name: card for card in _bundled_cards()})


#: Where a checkpoint is cached, relative to the cache root. The loader passes
#: ``cache_dir/models`` and the cache sweep walks the same directory; a third caller
#: spelling it a third way would report a cached model as absent.
MODEL_CACHE_SUBDIR = "models"


def checkpoint_path(card: ModelCard, cache_root: Path) -> Path:
    """Return where ``card``'s checkpoint is (or would be) cached under ``cache_root``."""
    return Path(cache_root) / MODEL_CACHE_SUBDIR / f"{card.name}.{card.version}.ckpt"


def model_status(card: ModelCard, cache_root: Path) -> dict[str, bool]:
    """Return what a caller can actually do with this model on this machine right now.

    The dataset registry answers the same question for data (:func:`~alleleforge.data.
    registry.dataset_status`), and four surfaces read that one derivation because each
    surface that derived it separately got a different answer. The model registry had no
    surface at all: the cards carry the licence, the intended and out-of-scope use, the
    known failure modes and the pinned checkpoint hash that gate every `--trained-*`
    flag and the whole leaderboard, and no shell could list them.

    ``available`` is deliberately stricter than "the file is there". The registry
    refuses to *load* an unpinned cached checkpoint exactly as it refuses to fetch one,
    so a card with no ``checkpoint_sha256`` is not usable however many bytes sit at its
    cache path — and reporting it as present is the presence-versus-permission confusion
    the dataset surfaces were corrected for.
    """
    pinned = card.checkpoint_sha256 is not None
    cached = checkpoint_path(card, cache_root).is_file()
    return {
        "pinned": pinned,
        "cached": cached,
        "available": pinned and cached,
        # "a fetch would work", not "the fields a fetch needs are set": a fetch also
        # needs consent, which is the caller's to give and not a property of the card.
        "fetchable": pinned and card.source_url is not None and not cached,
        "research_use": card.permits(ModelUse.RESEARCH),
        "commercial_use": card.permits(ModelUse.COMMERCIAL),
    }


def model_reason(status: dict[str, bool]) -> str:
    """Return why a model is or is not usable, without restating which of the two."""
    if status["available"]:
        return "cached and pinned"
    if not status["pinned"]:
        return "no pinned checksum, so it can be neither fetched nor loaded"
    if status["fetchable"]:
        return "fetch it with consent"
    return "pinned but not cached, and the card names no source to fetch from"


def model_presence(status: dict[str, bool]) -> str:
    """Return the one-line presence answer, shouting when nothing is there to use."""
    reason = model_reason(status)
    return reason if status["available"] else f"NOT AVAILABLE - {reason}"


def model_permission(status: dict[str, bool]) -> str:
    """Return the licence half, worded so it cannot be read as a presence claim."""
    if status["commercial_use"]:
        return "research + commercial use"
    if status["research_use"]:
        return "research use only"
    return "no use permitted"
