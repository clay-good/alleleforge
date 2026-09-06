"""Genome access & indexing (Phase 2).

Reference sequence retrieval (:mod:`.reference`), a content-addressed FM-index
for PAM-anchored candidate search (:mod:`.index`), and cross-build liftover plus
hg38-ambiguous-region flagging (:mod:`.coordinates`). This layer is pure
infrastructure: it knows about sequence and coordinates, not CRISPR chemistry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alleleforge.errors import ChecksumError, ConsentError
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

if TYPE_CHECKING:  # pragma: no cover - import-time only for type checkers
    from alleleforge.genome.reference import (
        BUILTIN_BUILDS,
        BuildDescriptor,
        FetchResult,
        ReferenceGenome,
    )

#: Re-exports resolved on first attribute access instead of at import.
#:
#: `reference` imports `pyfaidx`, which belongs to the optional `genome` extra, and a
#: package `__init__` runs for *any* submodule import — so `from
#: alleleforge.genome.coordinates import ...`, which `variant.resolver` does, dragged
#: pyfaidx in. That chained `benchmark -> scoring -> enumerate -> genome -> pyfaidx`
#: and made `aforge bench run` fail on a `pip install alleleforge[cli]` with a raw
#: `ModuleNotFoundError` — a command that touches no reference genome, requiring the
#: genome stack to import.
#:
#: Only the `reference` names are deferred; `coordinates` and `index` are pure and stay
#: eager. `from alleleforge.genome import ReferenceGenome` still works and still needs
#: pyfaidx — it just needs it when the name is used, not when the package is imported.
_LAZY_FROM_REFERENCE = ("BUILTIN_BUILDS", "BuildDescriptor", "FetchResult", "ReferenceGenome")


def __getattr__(name: str) -> object:
    """Resolve a deferred `reference` re-export on first access (PEP 562)."""
    if name in _LAZY_FROM_REFERENCE:
        from importlib import import_module

        return getattr(import_module("alleleforge.genome.reference"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
