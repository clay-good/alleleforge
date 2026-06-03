"""Per-chemistry reagent enumeration (Phases 7-9).

Strand-aware enumeration of the candidate reagents for each chemistry: SpCas9
guides (:mod:`.cas9`), base-editor windows (Phase 8), and pegRNAs (Phase 9).
Enumeration is pure sequence/geometry logic over the reference genome; scoring
and outcome prediction live in :mod:`alleleforge.scoring`.
"""

from __future__ import annotations

from alleleforge.enumerate.base_editor import (
    BASE_EDITORS,
    DEFAULT_WINDOW,
    BaseEditor,
    enumerate_base_edits,
)
from alleleforge.enumerate.cas9 import (
    DEFAULT_ACTIONABLE_RADIUS,
    DEFAULT_CUT_OFFSET,
    DEFAULT_HDR_ARM,
    enumerate_cas9,
    guide_context,
    hdr_donor,
)

__all__ = [
    "BASE_EDITORS",
    "DEFAULT_ACTIONABLE_RADIUS",
    "DEFAULT_CUT_OFFSET",
    "DEFAULT_HDR_ARM",
    "DEFAULT_WINDOW",
    "BaseEditor",
    "enumerate_base_edits",
    "enumerate_cas9",
    "guide_context",
    "hdr_donor",
]
