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

import warnings
from pathlib import Path
from typing import ClassVar

from alleleforge.config import get_settings
from alleleforge.model_zoo.checkout import checkout_revision
from alleleforge.model_zoo.registry import (
    MODEL_CACHE_SUBDIR,
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
            cache_dir = self._cache_dir or (get_settings().cache_dir / MODEL_CACHE_SUBDIR)
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

    def snapshot_revision(self) -> str | None:
        """Return the card's pinned upstream revision, or ``None`` if it pins none.

        Only meaningful on the "load by the model's own source" path — the one
        :meth:`resolve_weights` signals by returning ``None``. When a card pins a single
        artifact instead, that file *is* the pin and there is no revision to apply; the
        card schema refuses both at once so the two cannot disagree.

        Returns:
            A full 40-character commit sha, or ``None``.
        """
        snapshot = self._registry.get(self.card_name).source_snapshot
        return None if snapshot is None else snapshot.revision

    def check_checkout_revision(self, checkout: str | Path | None) -> str | None:
        """Compare a local checkout against the card's pinned revision.

        For the adapters that read a checkout rather than a checkpoint file, this is the
        only thing connecting ``source_snapshot`` to the directory actually on disk.
        Without it the pin is a statement about an upstream commit and nothing more.

        Warns rather than raises, and the distinction is deliberate. A newer checkout is
        a legitimate thing to have — a user comparing against upstream's latest is doing
        real work — so refusing would block it; and an unpacked tarball cannot report a
        revision at all, which is unverifiable rather than wrong. What must not happen is
        a run *silently* using something other than the pinned revision, because the
        result would carry a provenance claim nobody checked. So both cases say so, once,
        in the caller's own terms.

        Args:
            checkout: The directory the adapter was pointed at.

        Returns:
            The observed revision, or ``None`` if the card pins none or it cannot be read.
        """
        snapshot = self._registry.get(self.card_name).source_snapshot
        if snapshot is None:
            return None

        observed = checkout_revision(checkout)
        if observed is None:
            warnings.warn(
                f"{self.card_name}: cannot read a git revision from {checkout!r}, so this "
                f"run cannot be checked against the pinned "
                f"{snapshot.repo}@{snapshot.revision[:12]}. The result is still produced; "
                "its provenance names the pin, not what was actually loaded. Clone the "
                "repository (rather than unpacking a snapshot) to make this checkable.",
                UserWarning,
                stacklevel=3,
            )
            return None
        if observed != snapshot.revision:
            warnings.warn(
                f"{self.card_name}: the checkout at {checkout!r} is on {observed[:12]} "
                f"but this card pins {snapshot.repo}@{snapshot.revision[:12]}. The run "
                "proceeds — a newer checkout is a legitimate thing to score against — but "
                "it is not the pinned revision, so do not report it as one.",
                UserWarning,
                stacklevel=3,
            )
        return observed

    def model_checkpoint(self) -> ModelCheckpoint | None:
        """Return the resolved checkpoint provenance, or ``None`` if not yet loaded."""
        return self._checkpoint
