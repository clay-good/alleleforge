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
from collections.abc import Sequence

from alleleforge.model_zoo.registry import ModelCard, ModelRegistry, default_registry
from alleleforge.types.edit import AlleleOutcome, EditOutcome

#: Default maximum MMEJ deletion length considered (bp).
DEFAULT_MAX_DELETION = 20

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
        """Return the inDelphi model card (mechanism this baseline mirrors)."""
        return self._registry.get("indelphi")

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
    alleles = {a.allele for p in predictions for a in p.alleles}
    merged_prob = {
        allele: sum(_prob_of(p, allele) for p in predictions) / len(predictions)
        for allele in alleles
    }
    total = sum(merged_prob.values())
    merged = EditOutcome(
        alleles=tuple(
            AlleleOutcome(allele=a, probability=merged_prob[a] / total)
            for a in sorted(merged_prob, key=lambda a: merged_prob[a], reverse=True)
        ),
        partial=False,
    )
    # Agreement is how often the models pick the *same* most-likely allele: the
    # share that match the modal top allele. Identical models agree fully.
    tops = [p.most_likely.allele for p in predictions]
    consensus = max(set(tops), key=tops.count)
    agreement = tops.count(consensus) / len(tops)
    return merged, agreement


def _prob_of(outcome: EditOutcome, allele: str) -> float:
    """Return the probability ``outcome`` assigns to ``allele`` (0 if absent)."""
    return next((a.probability for a in outcome.alleles if a.allele == allele), 0.0)


class _ModelZooAdapter:
    """Shared base for the trained outcome adapters (lazy, license-gated)."""

    name = ""
    card_name = ""

    def __init__(self, *, registry: ModelRegistry | None = None) -> None:
        """Configure the model-card registry."""
        self._registry = registry or default_registry()

    def model_card(self) -> ModelCard:
        """Return the adapter's model card (raises if not registered)."""
        return self._registry.get(self.card_name)

    def predict(self, context: str, cut: int) -> EditOutcome:  # pragma: no cover - needs weights
        """Predict the indel spectrum (requires the trained model weights)."""
        raise NotImplementedError(
            f"{self.name} requires its trained weights; load them via the model zoo "
            "or use MicrohomologyOutcomePredictor"
        )


class InDelphiAdapter(_ModelZooAdapter):
    """Adapter to the trained inDelphi model (default outcome model)."""

    name = "inDelphi"
    card_name = "indelphi"


class LindelAdapter(_ModelZooAdapter):
    """Adapter to the trained Lindel model (optional)."""

    name = "Lindel"
    card_name = "lindel"


class XCrispAdapter(_ModelZooAdapter):
    """Adapter to the trained X-CRISP model (optional)."""

    name = "X-CRISP"
    card_name = "x-crisp"
