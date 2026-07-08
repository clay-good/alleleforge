"""Multi-objective ranking across chemistries on one footing.

Candidates from different chemistries arrive scored on different scales — a
nuclease guide carries an indel spectrum, a base editor an exact-allele
probability, a pegRNA a byproduct distribution. To order them *together* the
ranker projects every candidate onto four shared, higher-is-better objectives:

* **efficiency** — the calibrated on-target efficiency point estimate.
* **cleanliness** — the probability mass on the *intended* allele in the
  predicted outcome distribution (an off-target-free edit that produces the
  wrong product is not a good edit).
* **safety** — ``1 - worst-case off-target score``, computed against the
  **worst-affected ancestry**, never the average, so a guide that is safe on
  one population but dangerous in another is correctly penalized.
* **simplicity** — how few moving parts the reagent has (a single sgRNA beats a
  pegRNA + nicking guide + 3' motif).

The default ranking is a **transparent weighted sum** of the four, with the
spec's weights. Alongside the scalar order the ranker exposes the **Pareto
front** — the candidates that are not dominated on all four objectives at once —
so a user who weights the objectives differently can still see the
trade-off-optimal set.
"""

from __future__ import annotations

from dataclasses import dataclass

from alleleforge.types.candidate import DesignCandidate
from alleleforge.types.edit import Chemistry

#: The four ranking objectives, all higher-is-better, in display order.
OBJECTIVES = ("efficiency", "cleanliness", "safety", "simplicity")


@dataclass(frozen=True)
class RankingWeights:
    """Weights for the transparent weighted-sum ranking.

    The spec defaults favor efficiency, then weigh outcome cleanliness and
    off-target safety equally, with a light simplicity tie-breaker. Weights are
    normalized to sum to 1 so the composite score stays in ``[0, 1]``.
    """

    efficiency: float = 0.35
    cleanliness: float = 0.30
    safety: float = 0.30
    simplicity: float = 0.05

    def __post_init__(self) -> None:
        """Validate weights are non-negative and not all zero."""
        for name in OBJECTIVES:
            if getattr(self, name) < 0.0:
                raise ValueError(f"weight {name} must be non-negative")
        if self.total == 0.0:
            raise ValueError("ranking weights cannot all be zero")

    @property
    def total(self) -> float:
        """Return the sum of the four weights."""
        return self.efficiency + self.cleanliness + self.safety + self.simplicity

    def normalized(self) -> dict[str, float]:
        """Return the weights as a name->fraction map summing to 1."""
        total = self.total
        return {name: getattr(self, name) / total for name in OBJECTIVES}


#: The spec's default ranking weights.
DEFAULT_WEIGHTS = RankingWeights()

#: Per-chemistry base simplicity (single sgRNA = 1.0; a pegRNA + nick is more
#: cloning and more failure modes). Refined per candidate in :func:`_simplicity`.
_CHEMISTRY_SIMPLICITY: dict[Chemistry, float] = {
    Chemistry.CAS9_NUCLEASE: 1.00,
    Chemistry.BASE_ABE: 0.90,
    Chemistry.BASE_CBE: 0.90,
    Chemistry.PRIME: 0.55,
}


def _efficiency(candidate: DesignCandidate) -> tuple[float, bool, tuple[float, float] | None]:
    """Return an uncertainty-discounted efficiency estimate for ranking.

    Returns ``(estimate, in_distribution, interval)``. An in-distribution
    prediction is ranked on its point estimate; an out-of-distribution one is
    ranked on its **lower interval bound** instead, so a confident-looking OOD
    prediction cannot outrank an otherwise-equal in-distribution one. An
    unscored candidate contributes 0 and is treated as in-distribution.
    """
    p = candidate.efficiency
    if p is None:
        return 0.0, True, None
    if not p.in_distribution:
        return max(0.0, float(p.interval[0])), False, p.interval
    return float(p.value), True, p.interval


def _cleanliness(candidate: DesignCandidate) -> float:
    """Return the intended-allele probability mass (0 if no outcome)."""
    return float(candidate.outcome.p_intended) if candidate.outcome is not None else 0.0


def _safety(candidate: DesignCandidate) -> tuple[float, str | None]:
    """Return ``(safety, worst_ancestry)`` from the off-target report.

    Safety is ``1 - score`` of the worst-affected ancestry when the report
    carries ancestry annotation, else of the global worst site. A candidate
    with no off-target report (search skipped) is treated as fully safe but
    flagged elsewhere; that absence is surfaced in the candidate's flags.
    """
    report = candidate.offtarget
    if report is None:
        return 1.0, None
    worst = report.worst_ancestry()
    if worst is not None:
        ancestry, score = worst
        return 1.0 - score, ancestry
    return 1.0 - report.worst_score(), None


def _simplicity(candidate: DesignCandidate) -> float:
    """Return reagent simplicity in ``[0, 1]`` (more parts -> lower)."""
    base = _CHEMISTRY_SIMPLICITY.get(candidate.chemistry, 0.5)
    peg = candidate.pegrna
    if peg is not None:
        if peg.nicking_guide is not None:  # PE3/PE3b: a second guide to clone
            base -= 0.10
        if peg.is_epegrna:  # a 3' structural motif to append
            base -= 0.05
    return max(0.0, base)


@dataclass(frozen=True)
class CandidateScore:
    """The four objective scores and the composite for one candidate.

    Attributes:
        efficiency: The uncertainty-discounted efficiency estimate used in the
            composite — the point estimate in-distribution, the lower interval
            bound out-of-distribution.
        cleanliness: Intended-allele probability mass.
        safety: ``1 - worst-affected-ancestry off-target score``.
        simplicity: Reagent simplicity.
        worst_ancestry: The ancestry the safety term was computed against, if
            the report carried ancestry annotation.
        efficiency_in_distribution: ``False`` if the efficiency prediction was
            flagged out-of-distribution (and therefore ranked on its lower bound).
        efficiency_interval: The efficiency prediction's ``(low, high)`` interval,
            or ``None`` when the candidate is unscored.
        composite: The weighted-sum score that drives the order.
    """

    efficiency: float
    cleanliness: float
    safety: float
    simplicity: float
    worst_ancestry: str | None
    efficiency_in_distribution: bool
    efficiency_interval: tuple[float, float] | None
    composite: float

    def as_vector(self) -> tuple[float, float, float, float]:
        """Return the four objectives as a maximization vector."""
        return (self.efficiency, self.cleanliness, self.safety, self.simplicity)

    def explain(self) -> str:
        """Return a one-line human-readable score breakdown."""
        worst = f", worst-ancestry={self.worst_ancestry}" if self.worst_ancestry else ""
        if not self.efficiency_in_distribution and self.efficiency_interval is not None:
            eff = (
                f"eff {self.efficiency:.2f} (OOD, ranked on lower bound "
                f"{self.efficiency_interval[0]:.2f})"
            )
        elif self.efficiency_interval is not None:
            low, high = self.efficiency_interval
            eff = f"eff {self.efficiency:.2f} [{low:.2f}, {high:.2f}]"
        else:
            eff = f"eff {self.efficiency:.2f}"
        return (
            f"score {self.composite:.3f} "
            f"[{eff}, clean {self.cleanliness:.2f}, "
            f"safe {self.safety:.2f}, simple {self.simplicity:.2f}{worst}]"
        )


def score_candidate(
    candidate: DesignCandidate, *, weights: RankingWeights = DEFAULT_WEIGHTS
) -> CandidateScore:
    """Project one candidate onto the four objectives and the weighted sum.

    Args:
        candidate: The candidate to score.
        weights: The objective weights (default: the spec weights).

    Returns:
        The candidate's :class:`CandidateScore`.
    """
    eff, eff_in_dist, eff_interval = _efficiency(candidate)
    clean = _cleanliness(candidate)
    safe, worst_ancestry = _safety(candidate)
    simple = _simplicity(candidate)
    w = weights.normalized()
    composite = (
        w["efficiency"] * eff
        + w["cleanliness"] * clean
        + w["safety"] * safe
        + w["simplicity"] * simple
    )
    return CandidateScore(
        efficiency=eff,
        cleanliness=clean,
        safety=safe,
        simplicity=simple,
        worst_ancestry=worst_ancestry,
        efficiency_in_distribution=eff_in_dist,
        efficiency_interval=eff_interval,
        composite=composite,
    )


def _dominates(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    """Return ``True`` if ``a`` Pareto-dominates ``b`` (>= all, > at least one)."""
    return all(x >= y for x, y in zip(a, b, strict=True)) and any(
        x > y for x, y in zip(a, b, strict=True)
    )


def pareto_front(scores: list[CandidateScore]) -> tuple[int, ...]:
    """Return the indices of the Pareto-optimal scores (non-dominated set)."""
    vectors = [s.as_vector() for s in scores]
    front: list[int] = []
    for i, vi in enumerate(vectors):
        if not any(j != i and _dominates(vj, vi) for j, vj in enumerate(vectors)):
            front.append(i)
    return tuple(front)


@dataclass(frozen=True)
class RankingOutcome:
    """A ranked menu of candidates with scores, Pareto front, and rationale.

    Attributes:
        candidates: Candidates in ranked order (best first), each with its
            ranking rationale appended.
        scores: The :class:`CandidateScore` for each candidate, aligned to
            ``candidates``.
        pareto_front: Indices into ``candidates`` that are Pareto-optimal.
        weights: The normalized weights used for the composite score.
        rationale: How the ranking was computed.
    """

    candidates: tuple[DesignCandidate, ...]
    scores: tuple[CandidateScore, ...]
    pareto_front: tuple[int, ...]
    weights: dict[str, float]
    rationale: str


def rank_candidates(
    candidates: list[DesignCandidate],
    *,
    weights: RankingWeights = DEFAULT_WEIGHTS,
    max_per_chemistry: int | None = None,
) -> RankingOutcome:
    """Rank candidates across chemistries by the weighted-sum composite.

    Ties on the composite break by efficiency, then safety, then simplicity, so
    the order is total and deterministic. Each returned candidate has its
    score breakdown appended to its rationale, and the Pareto front is reported
    against the final order.

    Args:
        candidates: The pooled candidates from every chemistry.
        weights: The objective weights (default: the spec weights).
        max_per_chemistry: Keep at most this many candidates per chemistry. The cap
            is applied **after** the composite sort, so it keeps each chemistry's
            composite-best — never pruning a candidate that would top the composite
            on a vertical's local proxy (efficiency, `p_intended_exact`, …) before
            the composite is even computed. ``None`` keeps every candidate.

    Returns:
        A :class:`RankingOutcome` with the ordered candidates, their scores, the
        Pareto front, and the ranking rationale.
    """
    scored = [(c, score_candidate(c, weights=weights)) for c in candidates]
    scored.sort(
        key=lambda cs: (cs[1].composite, cs[1].efficiency, cs[1].safety, cs[1].simplicity),
        reverse=True,
    )
    if max_per_chemistry is not None:
        kept: list[tuple[DesignCandidate, CandidateScore]] = []
        per_chem: dict[Chemistry, int] = {}
        for cs in scored:
            chem = cs[0].chemistry
            if per_chem.get(chem, 0) >= max_per_chemistry:
                continue
            per_chem[chem] = per_chem.get(chem, 0) + 1
            kept.append(cs)
        scored = kept
    ranked: list[DesignCandidate] = []
    ordered_scores: list[CandidateScore] = []
    for candidate, score in scored:
        note = score.explain()
        rationale = f"{candidate.rationale}; {note}" if candidate.rationale else note
        ranked.append(candidate.model_copy(update={"rationale": rationale}))
        ordered_scores.append(score)
    front = pareto_front(ordered_scores)
    w = weights.normalized()
    n_ood = sum(1 for s in ordered_scores if not s.efficiency_in_distribution)
    ood_note = (
        f" {n_ood} out-of-distribution candidate(s) were ranked on their lower "
        "efficiency interval bound rather than the point estimate."
        if n_ood
        else ""
    )
    rationale = (
        "Ranked by a weighted sum of four higher-is-better objectives "
        f"(efficiency {w['efficiency']:.2f}, cleanliness {w['cleanliness']:.2f}, "
        f"safety {w['safety']:.2f}, simplicity {w['simplicity']:.2f}); the safety "
        "term uses the worst-affected ancestry and the efficiency term is "
        f"uncertainty-discounted.{ood_note} The Pareto front lists the "
        f"{len(front)} candidate(s) not dominated on all four objectives."
    )
    return RankingOutcome(
        candidates=tuple(ranked),
        scores=tuple(ordered_scores),
        pareto_front=front,
        weights=w,
        rationale=rationale,
    )
