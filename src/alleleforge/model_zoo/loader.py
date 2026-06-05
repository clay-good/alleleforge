"""The shared weight-resolution gate for every trained scorer / backbone.

Every real model in AlleleForge — the sequence backbone and the per-chemistry
trained adapters (efficiency and outcome) — loads its weights the same way: behind
the **license-gated, consent-required, checksum-verified** model zoo. :class:`WeightGate`
is that single implementation, mixed into each adapter so the consent flow lives in
one place rather than copied per chemistry.

Two paths, chosen by the card:

* the card pins a ``checkpoint_sha256`` ⇒ the full
  :meth:`~alleleforge.model_zoo.registry.ModelRegistry.checkpoint` download +
  checksum flow runs and a verified local path is returned;
* otherwise ⇒ the lighter
  :meth:`~alleleforge.model_zoo.registry.ModelRegistry.authorize` license + consent
  gate runs (the weights are then loaded by the model's own integrity-checked
  loader, e.g. a HuggingFace repo id).

Either way the resolved :class:`~alleleforge.types.provenance.ModelCheckpoint` is
recorded for the result provenance block, and a download without consent, a
license that forbids the use, or a bad checksum fails loudly.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from alleleforge.config import get_settings
from alleleforge.model_zoo.registry import (
    Downloader,
    ModelRegistry,
    ModelUse,
    default_registry,
)
from alleleforge.types.provenance import ModelCheckpoint


class WeightGate:
    """Mixin giving a model the consent-gated model-zoo weight-resolution flow.

    Subclasses set :attr:`card_name` to the model-zoo card that gates them and
    call :meth:`resolve_weights` before loading any tensors.
    """

    #: The model-zoo card key gating this model (license + consent + checksum).
    card_name: ClassVar[str] = ""

    def __init__(
        self,
        *,
        registry: ModelRegistry | None = None,
        use: ModelUse = ModelUse.RESEARCH,
        consent: bool = False,
        cache_dir: str | Path | None = None,
        downloader: Downloader | None = None,
    ) -> None:
        """Configure the model-zoo gate and consent for weight download.

        Args:
            registry: Model-card registry (defaults to the bundled cards).
            use: The use the weights are loaded for (drives the license gate).
            consent: Must be ``True`` to authorize any weight download.
            cache_dir: Override for the checkpoint cache (pinned-artifact path).
            downloader: Injected fetcher for the pinned-artifact path (tests).
        """
        self._registry = registry or default_registry()
        self._use = use
        self._consent = consent
        self._cache_dir = cache_dir
        self._downloader = downloader
        self._checkpoint: ModelCheckpoint | None = None

    def resolve_weights(self) -> str | None:
        """Resolve the model's weights through the consent-gated model zoo.

        Returns:
            A verified local checkpoint path (pinned-artifact path), or ``None``
            to load by the model's own source after the license + consent gate.

        Raises:
            ConsentError: If a download is needed but consent was not given.
            LicenseError: If the card's license forbids the requested use.
            ChecksumError: If a pinned artifact fails verification.
        """
        card = self._registry.get(self.card_name)
        if card.checkpoint_sha256 is not None:
            cache_dir = self._cache_dir or (get_settings().cache_dir / "models")
            path, checkpoint = self._registry.checkpoint(
                self.card_name,
                cache_dir=cache_dir,
                use=self._use,
                consent=self._consent,
                downloader=self._downloader,
            )
            self._checkpoint = checkpoint
            return str(path)
        self._checkpoint = self._registry.authorize(
            self.card_name, use=self._use, consent=self._consent
        )
        return None

    def model_checkpoint(self) -> ModelCheckpoint | None:
        """Return the resolved checkpoint provenance, or ``None`` if not yet loaded."""
        return self._checkpoint
