"""Genome access & indexing (Phase 2).

Reference sequence retrieval (:mod:`.reference`), a content-addressed FM-index
for PAM-anchored candidate search (:mod:`.index`), and cross-build liftover plus
hg38-ambiguous-region flagging (:mod:`.coordinates`). This layer is pure
infrastructure: it knows about sequence and coordinates, not CRISPR chemistry.
"""

from __future__ import annotations

from alleleforge.genome.coordinates import (
    DEFAULT_RECOMMENDED_BUILD,
    HG38_DIFFICULT_REGIONS,
    AmbiguousRegion,
    Liftover,
    ReferenceRecommendation,
    RegionFlagKind,
    flag_ambiguous_regions,
)
from alleleforge.genome.index import (
    SIZE_WARN_THRESHOLD,
    FMIndex,
    GenomeIndex,
    PamHit,
    native_fm_available,
    native_sais_available,
)
from alleleforge.genome.reference import (
    BUILTIN_BUILDS,
    BuildDescriptor,
    ChecksumError,
    ConsentError,
    FetchResult,
    ReferenceGenome,
)

__all__ = [
    "BUILTIN_BUILDS",
    "DEFAULT_RECOMMENDED_BUILD",
    "HG38_DIFFICULT_REGIONS",
    "SIZE_WARN_THRESHOLD",
    "AmbiguousRegion",
    "BuildDescriptor",
    "ChecksumError",
    "ConsentError",
    "FMIndex",
    "FetchResult",
    "GenomeIndex",
    "Liftover",
    "PamHit",
    "ReferenceGenome",
    "ReferenceRecommendation",
    "RegionFlagKind",
    "flag_ambiguous_regions",
    "native_fm_available",
    "native_sais_available",
]
