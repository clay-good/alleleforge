"""Design orchestration (Phases 7-10).

Per-chemistry design verticals that assemble scored
:class:`~alleleforge.types.candidate.DesignCandidate`s, starting with the SpCas9
nuclease slice (:mod:`.cas9`). The Phase 10 designer adds variant routing,
multi-chemistry candidate menus, and cross-chemistry ranking on top of these.
"""

from __future__ import annotations

from alleleforge.design.base_editor import design_base_editor
from alleleforge.design.cas9 import design_cas9
from alleleforge.design.designer import design
from alleleforge.design.prime import design_prime
from alleleforge.design.ranking import (
    DEFAULT_WEIGHTS,
    CandidateScore,
    RankingOutcome,
    RankingWeights,
    rank_candidates,
    score_candidate,
)
from alleleforge.design.routing import (
    ROUTING_RULES,
    ChemistryDecision,
    RoutingRule,
    eligible_chemistries,
    route,
)

__all__ = [
    "DEFAULT_WEIGHTS",
    "ROUTING_RULES",
    "CandidateScore",
    "ChemistryDecision",
    "RankingOutcome",
    "RankingWeights",
    "RoutingRule",
    "design",
    "design_base_editor",
    "design_cas9",
    "design_prime",
    "eligible_chemistries",
    "rank_candidates",
    "route",
    "score_candidate",
]
