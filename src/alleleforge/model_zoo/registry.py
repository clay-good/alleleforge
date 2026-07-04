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
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from alleleforge.types.provenance import ModelCheckpoint

#: Directory of bundled model cards shipped with AlleleForge.
CARDS_DIR = Path(__file__).parent / "cards"

#: A downloader writes the artifact at ``url`` to ``dest`` (injected for tests).
Downloader = Callable[[str, Path], None]

#: Licenses AlleleForge refuses to load under any use (no redistribution / unknown).
FORBIDDEN_LICENSES = frozenset({"proprietary", "none", "unknown", "all-rights-reserved"})

#: Substrings marking a non-commercial license (blocks commercial use).
_NONCOMMERCIAL_MARKERS = ("-nc", "noncommercial", "non-commercial", "research-only")


class ModelUse(StrEnum):
    """The use a checkpoint is being loaded for (drives the license gate)."""

    RESEARCH = "research"
    COMMERCIAL = "commercial"


class ConsentError(RuntimeError):
    """Raised when a download is needed but the caller withheld consent."""


class ChecksumError(RuntimeError):
    """Raised when a checkpoint is unverifiable or fails checksum verification."""


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
    known_failure_modes: tuple[str, ...] = ()
    checkpoint_sha256: str | None = None
    source_url: str | None = None

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
            if not consent:
                raise ConsentError(
                    f"checkpoint for {name!r} is not cached; pass consent=True to download "
                    f"from {card.source_url}"
                )
            if card.checkpoint_sha256 is None:
                raise ChecksumError(
                    f"model {name!r} pins no checkpoint hash; refusing to fetch an unverifiable "
                    "artifact"
                )
            if card.source_url is None:
                raise ConsentError(f"model {name!r} has no source_url to download from")
            path.parent.mkdir(parents=True, exist_ok=True)
            (downloader or _default_downloader)(card.source_url, path)
            _verify_sha256(path, card.checkpoint_sha256)
        elif card.checkpoint_sha256 is not None:
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
        if not consent:
            raise ConsentError(
                f"loading model {name!r} downloads weights from {card.source_url}; "
                "pass consent=True to authorize the fetch"
            )
        return card.to_checkpoint()


#: The default registry, populated from the bundled cards on first use.
def default_registry() -> ModelRegistry:
    """Return a registry built from the bundled model cards."""
    return ModelRegistry.from_cards_dir()
