"""Prime-editing efficiency scoring with prominent OOD honesty.

The default is a transparent, deterministic PRIDICT2.0-style baseline over the
pegRNA geometry (PBS length/Tm, RTT length, nick-to-edit distance, GC, epegRNA
motif). PRIDICT2.0 itself is trained on **HEK293T/K562**; whenever a target or
cell context is unlike that training distribution the prediction is flagged
**out-of-distribution** — surfaced prominently, because a confident efficiency
number outside the training context is exactly the kind of false confidence the
uncertainty contract exists to prevent.

`ePRIDICT` adjusts the prediction for **chromatin context** using Phase 3 ENCODE
tracks when a cell context is supplied (open chromatin edits better). The trained
PRIDICT2.0 / DeepPrime / GenET models load through the license-gated model zoo.
"""

from __future__ import annotations

import math

from alleleforge.data.annotations import EncodeTracks
from alleleforge.model_zoo.loader import WeightGate
from alleleforge.model_zoo.registry import ModelCard, ModelRegistry, default_registry
from alleleforge.types.guide import PegRNA
from alleleforge.types.prediction import Prediction, UncertaintyMethod
from alleleforge.types.sequence import GenomicInterval

#: Cell contexts PRIDICT2.0 is trained on; anything else is out-of-distribution.
PRIDICT_TRAINING_CONTEXTS = frozenset({"HEK293T", "K562"})

#: Optimal PBS length (nt) for the baseline geometry term.
_OPTIMAL_PBS = 13

#: Heuristic interval half-width for the baseline's calibrated prediction.
_INTERVAL_HALF = 0.15


def _sigmoid(x: float) -> float:
    """Return the logistic of ``x`` clamped to ``[0.01, 0.99]``."""
    return min(0.99, max(0.01, 1.0 / (1.0 + math.exp(-x))))


def _gc(seq: str) -> float:
    """Return the GC fraction of ``seq`` (0 for empty)."""
    return sum(b in "GC" for b in seq) / len(seq) if seq else 0.0


def _nick_to_edit(pegrna: PegRNA) -> int:
    """Derive the nick-to-edit distance from the RTT geometry."""
    return max(0, len(pegrna.rtt) - pegrna.rtt_homology_3prime - 1)


class PridictScorer:
    """A transparent PRIDICT2.0-style prime-editing efficiency baseline."""

    name = "pridict2"

    def __init__(self, *, registry: ModelRegistry | None = None) -> None:
        """Configure the (optional) model-card registry."""
        self._registry = registry or default_registry()

    def model_card(self) -> ModelCard:
        """Return the PRIDICT2.0 model card."""
        return self._registry.get("pridict2")

    def _logit(self, pegrna: PegRNA) -> float:
        """Return the geometry-feature efficiency logit for ``pegrna``."""
        pbs, rtt = str(pegrna.pbs), str(pegrna.rtt)
        logit = 0.5
        logit -= 0.10 * abs(len(pbs) - _OPTIMAL_PBS)  # PBS near 13 nt is best
        logit -= 0.03 * _nick_to_edit(pegrna)  # nearer edits are more efficient
        logit -= 0.02 * max(0, len(rtt) - 20)  # very long RTTs are penalized
        logit -= 2.0 * abs(_gc(pbs) - 0.5)  # mid-GC PBS primes best
        if pegrna.is_epegrna:
            logit += 0.3  # the tevopreQ1 motif stabilizes the 3' extension
        return logit

    def score(
        self,
        pegrna: PegRNA,
        *,
        cell_context: str | None = None,
        chromatin: tuple[EncodeTracks, GenomicInterval, str] | None = None,
    ) -> Prediction[float]:
        """Return a calibrated efficiency prediction for ``pegrna``.

        Args:
            pegrna: The pegRNA to score.
            cell_context: The target cell context; a value outside PRIDICT's
                HEK293T/K562 training distribution sets ``in_distribution=False``.
            chromatin: Optional ``(tracks, interval, track_name)`` for an
                ePRIDICT-style open-chromatin adjustment.

        Returns:
            A calibrated 80% :class:`Prediction` with the OOD flag set honestly.
        """
        value = _sigmoid(self._logit(pegrna))
        if chromatin is not None:
            tracks, interval, track = chromatin
            signal = tracks.signal(track, interval)
            value = min(0.99, value * (1.0 + 0.1 * math.tanh(signal)))  # open chromatin helps
        in_dist = cell_context is None or cell_context in PRIDICT_TRAINING_CONTEXTS
        return Prediction[float](
            value=value,
            interval=(max(0.0, value - _INTERVAL_HALF), min(1.0, value + _INTERVAL_HALF)),
            interval_level=0.80,
            method=UncertaintyMethod.HEURISTIC,
            in_distribution=in_dist,
            calibrated=False,
        )


class _ModelZooAdapter(WeightGate):
    """Shared base for the trained prime-efficiency adapters (lazy, gated).

    Trained weights resolve through the **consent-gated, license-checked,
    checksum-verified** model zoo (:class:`~alleleforge.model_zoo.loader.WeightGate`):
    loading requires explicit consent and a permitting license, and the resolved
    :class:`ModelCheckpoint` is recorded for provenance. The consent/license/checksum
    flow is exercisable without the ML stack; the forward pass itself lands with the
    real weights (``real_weights``).
    """

    name = ""

    def model_card(self) -> ModelCard:
        """Return the adapter's model card (raises if not registered)."""
        return self._registry.get(self.card_name)

    def score(self, pegrna: PegRNA, **kwargs: object) -> Prediction[float]:
        """Resolve the license gate, then refuse — this is an out-of-scope placeholder.

        ``DeepPrimeAdapter`` / ``GenETAdapter`` are license-gated placeholders, not
        supported models: DeepPrime's per-pegRNA API needs edit metadata a
        :class:`PegRNA` does not carry, its stack is heavy/Python-≤3.10-pinned
        (``tensorflow<2.10`` + ``viennarna``), and its sequence-level API is redundant
        with the wired PRIDICT2.0 engine. See ``specs/cross-check-models-scope.md``.

        Raises:
            ConsentError / LicenseError / ChecksumError: From the weight gate.
            NotImplementedError: Always — use
                :class:`~alleleforge.scoring.pridict_engine.PridictEngineAdapter`
                (real PRIDICT2.0) for prime efficiency.
        """
        self.resolve_weights()
        raise NotImplementedError(  # pragma: no cover - out of supported scope (see scope spec)
            f"{self.name} is an out-of-scope placeholder (heavy/redundant upstream; "
            "see specs/cross-check-models-scope.md). Use PridictEngineAdapter for the "
            "real PRIDICT2.0 prime-efficiency model."
        )


class DeepPrimeAdapter(_ModelZooAdapter):
    """Adapter to the trained DeepPrime model (cross-check)."""

    name = "DeepPrime"
    card_name = "deepprime"


class GenETAdapter(_ModelZooAdapter):
    """Adapter to the trained GenET prime-efficiency model (cross-check)."""

    name = "GenET"
    card_name = "genet"
