"""Design orchestration (Phases 7-10).

Per-chemistry design verticals that assemble scored
:class:`~alleleforge.types.candidate.DesignCandidate`s, starting with the SpCas9
nuclease slice (:mod:`.cas9`). The Phase 10 designer adds variant routing,
multi-chemistry candidate menus, and cross-chemistry ranking on top of these.
"""

from __future__ import annotations

from alleleforge.design.base_editor import design_base_editor
from alleleforge.design.cas9 import design_cas9

__all__ = ["design_base_editor", "design_cas9"]
