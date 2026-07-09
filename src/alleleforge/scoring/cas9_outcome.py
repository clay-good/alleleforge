"""SpCas9 nuclease edit-outcome (indel spectrum) prediction.

Predicts the distribution over repair alleles at a blunt cut. The default is a
transparent, deterministic **microhomology / MMEJ** baseline reproducing the
mechanism behind inDelphi (Shen et al., *Nature* 2018): deletions are templated
by microhomologies flanking the cut (longer microhomology and shorter deletion
are favored), and 1-bp insertions are templated by the nucleotide 5' of the cut.

The trained inDelphi, Lindel, and X-CRISP models load through the model zoo
(license-gated) when present; the shipped default is the documented baseline, not
the fitted models. An ensemble mode merges several predictors and reports their
top-allele **agreement** as an inter-model uncertainty signal.
"""

from __future__ import annotations

import math
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from alleleforge.model_zoo.loader import WeightGate
from alleleforge.model_zoo.registry import (
    Downloader,
    ModelCard,
    ModelRegistry,
    ModelUse,
    default_registry,
)
from alleleforge.types.edit import AlleleOutcome, EditOutcome

#: Default maximum MMEJ deletion length considered (bp).
DEFAULT_MAX_DELETION = 20

#: Lindel's fixed window geometry: a 60-bp sequence with the cut at index 30.
_LINDEL_FLANK = 30

#: Relative weight of a templated 1-bp insertion vs. the MMEJ deletion pool.
_INSERTION_BASE_WEIGHT = 1.0


def _mh_deletions(seq: str, cut: int, max_del: int) -> list[tuple[str, float, int]]:
    """Return ``(allele, weight, del_len)`` for microhomology-mediated deletions.

    A microhomology is a substring repeated with one copy 5' of the cut and one
    3' of it; the MMEJ deletion joins them, removing the intervening sequence. The
    weight favors longer microhomology and shorter deletions (the inDelphi shape).
    """
    n = len(seq)
    out: list[tuple[str, float, int]] = []
    for i in range(cut):
        for j in range(cut, n):
            m = 0
            while i + m < j and j + m < n and seq[i + m] == seq[j + m]:
                m += 1
            if m < 1:
                continue
            del_len = j - i
            if del_len > max_del:
                continue
            weight = math.exp(-del_len / 8.0) * (1.0 + 0.5 * m)
            out.append((f"del{del_len}:mh{m}@{i}", weight, del_len))
    return out


def _insertions(seq: str, cut: int) -> list[tuple[str, float]]:
    """Return ``(allele, weight)`` for templated 1-bp insertions at the cut."""
    out: list[tuple[str, float]] = []
    if cut >= 1:
        base = seq[cut - 1]  # the -1 nucleotide templates the dominant +1 insertion
        bias = {"A": 1.0, "T": 1.0, "G": 0.7, "C": 0.7}.get(base, 0.8)
        out.append((f"ins1:{base}", _INSERTION_BASE_WEIGHT * bias))
    if cut < len(seq):
        out.append((f"ins1:{seq[cut]}", _INSERTION_BASE_WEIGHT * 0.3))
    return out


class MicrohomologyOutcomePredictor:
    """A transparent microhomology/MMEJ + 1-bp-insertion outcome baseline."""

    name = "indelphi-mh-baseline"

    def __init__(self, *, registry: ModelRegistry | None = None) -> None:
        """Configure the (optional) model-card registry."""
        self._registry = registry or default_registry()

    def model_card(self) -> ModelCard:
        """Return the heuristic baseline's own card.

        This is a transparent MMEJ heuristic, not the trained inDelphi model, so
        it carries its own ``indelphi-mh-baseline`` card rather than the trained
        ``indelphi`` card — otherwise a default run's provenance records
        trained-only training data / failure modes for a heuristic's numbers and a
        re-run from that checkpoint reproduces different numbers. The opt-in
        trained adapter keeps the ``indelphi`` card.
        """
        return self._registry.get("indelphi-mh-baseline")

    def predict(
        self,
        context: str,
        cut: int,
        *,
        max_del: int = DEFAULT_MAX_DELETION,
        mark_frameshift: bool = False,
    ) -> EditOutcome:
        """Return the predicted indel-outcome distribution at ``cut``.

        Args:
            context: The local plus-strand sequence around the cut.
            cut: The 0-based cut index within ``context`` (between ``cut-1`` and
                ``cut``).
            max_del: Maximum MMEJ deletion length to consider.
            mark_frameshift: Mark frameshifting alleles (out-of-frame indels) as
                intended — the designer sets this for a knock-out intent.

        Returns:
            A normalized :class:`EditOutcome` over the modeled alleles.

        Raises:
            ValueError: If ``cut`` is outside ``context``.
        """
        seq = context.upper()
        if not 0 <= cut <= len(seq):
            raise ValueError(f"cut {cut} outside context of length {len(seq)}")
        entries: list[tuple[str, float, int]] = _mh_deletions(seq, cut, max_del)
        entries += [(allele, w, 0) for allele, w in _insertions(seq, cut)]
        # An unmodeled-byproduct floor keeps the model honest (wild-type / other).
        entries.append(("other", 0.05 * sum(w for _a, w, _d in entries) or 0.01, 0))
        total = sum(w for _a, w, _d in entries)
        outcomes = tuple(
            AlleleOutcome(
                allele=allele,
                probability=w / total,
                is_intended=mark_frameshift and _is_frameshift(allele, del_len),
            )
            for allele, w, del_len in entries
        )
        return EditOutcome(alleles=outcomes, partial=False)


def _is_frameshift(allele: str, del_len: int) -> bool:
    """Return ``True`` if an allele shifts the reading frame (out of frame)."""
    if allele.startswith("ins1"):
        return True  # a 1-bp insertion is always a frameshift
    return del_len % 3 != 0


def ensemble_outcome(predictions: Sequence[EditOutcome]) -> tuple[EditOutcome, float]:
    """Merge outcome distributions and report top-allele agreement.

    Args:
        predictions: Per-model :class:`EditOutcome` distributions.

    Returns:
        ``(merged, agreement)`` where ``merged`` averages the per-allele
        probabilities and ``agreement`` is the fraction of models whose most-likely
        allele equals the consensus most-likely allele — an inter-model
        uncertainty signal in ``[0, 1]``.

    Raises:
        ValueError: If ``predictions`` is empty.
    """
    if not predictions:
        raise ValueError("ensemble_outcome needs at least one prediction")
    # Build the merged distribution over a *sorted* allele set: a set comprehension
    # iterates in hash-seed-dependent order, which would make the dict insertion
    # order (hence the float summation order of `total`) and any probability-tie
    # order vary run-to-run — breaking the byte-determinism the provenance contract
    # promises. Sorting the allele order fixes both.
    alleles = sorted({a.allele for p in predictions for a in p.alleles})
    merged_prob = {
        allele: sum(_prob_of(p, allele) for p in predictions) / len(predictions)
        for allele in alleles
    }
    total = sum(merged_prob.values())
    merged = EditOutcome(
        alleles=tuple(
            AlleleOutcome(allele=a, probability=merged_prob[a] / total)
            # Total order: probability descending, then allele name — a tie never
            # falls to hash-dependent order.
            for a in sorted(merged_prob, key=lambda a: (-merged_prob[a], a))
        ),
        partial=False,
    )
    # Agreement is how often the models pick the *same* most-likely allele: the
    # share that match the modal top allele. Identical models agree fully. Break a
    # count tie by allele name (`sorted`) so the consensus is deterministic.
    tops = [p.most_likely.allele for p in predictions]
    consensus = max(sorted(set(tops)), key=tops.count)
    agreement = tops.count(consensus) / len(tops)
    return merged, agreement


def _prob_of(outcome: EditOutcome, allele: str) -> float:
    """Return the probability ``outcome`` assigns to ``allele`` (0 if absent)."""
    return next((a.probability for a in outcome.alleles if a.allele == allele), 0.0)


class _ModelZooAdapter(WeightGate):
    """Shared base for the trained outcome adapters (lazy, license-gated).

    Trained weights resolve through the **consent-gated, checksum-verified** model
    zoo (:class:`~alleleforge.model_zoo.loader.WeightGate`); the forward pass over
    those weights lands with the real-weights integration. Use
    :class:`MicrohomologyOutcomePredictor` meanwhile.
    """

    name = ""

    def model_card(self) -> ModelCard:
        """Return the adapter's model card (raises if not registered)."""
        return self._registry.get(self.card_name)

    def predict(self, context: str, cut: int) -> EditOutcome:
        """Resolve the license gate, then refuse — this is an out-of-scope placeholder.

        ``InDelphiAdapter`` / ``XCrispAdapter`` are license-gated placeholders, not
        supported models: their upstreams are dependency-rotted (TF1/Theano, old
        ``scikit-learn``, ``mpi4py``) and redundant with the wired **Lindel** model.
        See ``specs/cross-check-models-scope.md``.

        Raises:
            ConsentError / LicenseError / ChecksumError: From the weight gate.
            NotImplementedError: Always — use :class:`LindelAdapter` (real) or
                :class:`MicrohomologyOutcomePredictor` (baseline) for this axis.
        """
        self.resolve_weights()
        raise NotImplementedError(  # pragma: no cover - out of supported scope (see scope spec)
            f"{self.name} is an out-of-scope placeholder (dependency-rotted/redundant "
            "upstream; see specs/cross-check-models-scope.md). Use LindelAdapter for "
            "the real SpCas9 indel-outcome model."
        )


class InDelphiAdapter(_ModelZooAdapter):
    """Adapter to the trained inDelphi model (default outcome model)."""

    name = "inDelphi"
    card_name = "indelphi"


def _lindel_window(context: str, cut: int) -> str:
    """Return Lindel's 60-bp input window (30 bp each side of ``cut``).

    Raises:
        ValueError: If ``context`` lacks 30 bp on either side of ``cut``.
    """
    seq = context.upper()
    if not _LINDEL_FLANK <= cut <= len(seq) - _LINDEL_FLANK:
        raise ValueError(
            f"Lindel needs >={_LINDEL_FLANK} bp flanking the cut (cut={cut}, len={len(seq)})"
        )
    return seq[cut - _LINDEL_FLANK : cut + _LINDEL_FLANK]


def _lindel_outcome(
    probs: Sequence[float],
    labels: Sequence[str],
    frameshift: Sequence[float],
    *,
    mark_frameshift: bool,
    top_k: int,
) -> EditOutcome:
    """Map a Lindel class distribution to a normalized :class:`EditOutcome`.

    Keeps the ``top_k`` most probable indel classes verbatim and buckets the tail
    into ``other_frameshift`` / ``other_inframe`` so the **total** frameshift
    probability is preserved exactly (it equals Lindel's frameshift ratio when
    ``mark_frameshift`` is set). Pure — unit-tested without the model.
    """
    order = sorted(range(len(probs)), key=lambda i: probs[i], reverse=True)
    alleles: list[AlleleOutcome] = [
        AlleleOutcome(
            allele=labels[i],
            probability=probs[i],
            is_intended=mark_frameshift and frameshift[i] >= 0.5,
        )
        for i in order[:top_k]
    ]
    rest = order[top_k:]
    fs_tail = sum(probs[i] for i in rest if frameshift[i] >= 0.5)
    inf_tail = sum(probs[i] for i in rest if frameshift[i] < 0.5)
    if fs_tail > 0:
        alleles.append(
            AlleleOutcome(
                allele="other_frameshift", probability=fs_tail, is_intended=mark_frameshift
            )
        )
    if inf_tail > 0:
        alleles.append(
            AlleleOutcome(allele="other_inframe", probability=inf_tail, is_intended=False)
        )
    return EditOutcome(alleles=tuple(alleles), partial=False)


def _require_lindel(repo: Path) -> tuple[Any, Any, Any]:  # pragma: no cover - needs the checkout
    """Import Lindel + load its weights from a checkout, or raise a helpful error."""
    import pickle

    try:
        import numpy  # noqa: F401  (Lindel needs it; surfaced as a clear error if absent)

        if str(repo) not in sys.path:
            sys.path.insert(0, str(repo))
        import Lindel
        from Lindel.Predictor import gen_prediction

        lp = Lindel.__path__[0]
        with open(os.path.join(lp, "Model_weights.pkl"), "rb") as handle:
            wb = pickle.load(handle)
        with open(os.path.join(lp, "model_prereq.pkl"), "rb") as handle:
            prereq = pickle.load(handle)
    except (ImportError, FileNotFoundError) as exc:
        raise RuntimeError(
            "the trained Lindel model requires NumPy and a Lindel checkout. Clone "
            "https://github.com/shendurelab/Lindel and set $ALLELEFORGE_LINDEL_REPO; "
            "see specs/cas9-outcome-integration.md"
        ) from exc
    return gen_prediction, wb, prereq


class LindelAdapter(_ModelZooAdapter):
    """The real trained Lindel SpCas9 indel-outcome model (consent-gated, opt-in).

    Runs Lindel's logistic-regression model (Chen et al., *Nucleic Acids Res* 2019)
    on the 60-bp window around the cut and maps its 557-class indel distribution to
    a normalized :class:`EditOutcome`, preserving the frameshift mass exactly. Lindel
    ships as a Git repo (not a PyPI package), so point the adapter at a checkout via
    ``repo_dir`` / ``$ALLELEFORGE_LINDEL_REPO``. Pure NumPy (no torch); gated behind
    the ``real_weights`` marker so CI stays weight-free.
    """

    name = "Lindel"
    card_name = "lindel"

    def __init__(
        self,
        *,
        repo_dir: str | Path | None = None,
        top_k: int = 24,
        registry: ModelRegistry | None = None,
        use: ModelUse = ModelUse.RESEARCH,
        consent: bool = False,
        cache_dir: str | Path | None = None,
        downloader: Downloader | None = None,
    ) -> None:
        """Configure the Lindel checkout, output truncation, and model-zoo gate.

        Args:
            repo_dir: Path to a Lindel checkout. Defaults to ``$ALLELEFORGE_LINDEL_REPO``.
            top_k: Keep this many top indel classes verbatim (tail is bucketed).
            registry: Model-card registry (defaults to the bundled cards).
            use: The use the weights are loaded for (drives the license gate).
            consent: Must be ``True`` to authorize use of the weights.
            cache_dir: Override for the checkpoint cache (unused on this path).
            downloader: Injected fetcher (unused on this path).
        """
        super().__init__(
            registry=registry,
            use=use,
            consent=consent,
            cache_dir=cache_dir,
            downloader=downloader,
        )
        self._repo = Path(repo_dir or os.environ.get("ALLELEFORGE_LINDEL_REPO", ""))
        self._top_k = top_k

    def predict(
        self,
        context: str,
        cut: int,
        *,
        max_del: int = DEFAULT_MAX_DELETION,
        mark_frameshift: bool = False,
    ) -> EditOutcome:
        """Predict the indel spectrum at ``cut`` with the trained Lindel model.

        Raises:
            ValueError: If the context is too short or has no NGG PAM for Lindel.
            ConsentError / LicenseError: From the model-zoo gate.
        """
        window = _lindel_window(context, cut)
        self.resolve_weights()  # consent + license gate; records provenance
        return self._predict_with_model(
            window, mark_frameshift
        )  # pragma: no cover - needs checkout

    def _predict_with_model(  # pragma: no cover - needs the checkout + NumPy
        self, window: str, mark_frameshift: bool
    ) -> EditOutcome:
        """Run Lindel on a 60-bp window and assemble the outcome distribution."""
        gen_prediction, wb, prereq = _require_lindel(self._repo)
        result = gen_prediction(window, wb, prereq)
        if isinstance(result, str):  # Lindel reports e.g. a missing PAM as a string
            raise ValueError(f"Lindel could not score the window: {result}")
        y_hat, _frameshift_ratio = result
        label, _rev, _feat, frame_shift = prereq
        inv = {idx: lbl for lbl, idx in label.items()}
        probs = [float(p) for p in y_hat]
        labels = [inv[i] for i in range(len(probs))]
        fs = [float(x) for x in frame_shift]
        return _lindel_outcome(
            probs, labels, fs, mark_frameshift=mark_frameshift, top_k=self._top_k
        )


class XCrispAdapter(_ModelZooAdapter):
    """Adapter to the trained X-CRISP model (optional)."""

    name = "X-CRISP"
    card_name = "x-crisp"
