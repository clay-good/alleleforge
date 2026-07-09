"""The typed domain vocabulary the whole system speaks (Phase 1).

This package is the source of truth for strandedness, coordinate systems,
ambiguity codes, the uncertainty contract, and every serializable result type.
It is deliberately free of I/O, genome access, and model code so that every
higher layer can depend on it without pulling heavy dependencies.

Coordinates are 0-based half-open internally; the uncertainty contract forbids
bare-float predictions (see :class:`Prediction`).
"""

from __future__ import annotations

from alleleforge.types.candidate import DesignCandidate, RankedMenu
from alleleforge.types.edit import (
    AlleleOutcome,
    Chemistry,
    EditIntent,
    EditOutcome,
    EditStrategy,
)
from alleleforge.types.guide import (
    DEFAULT_SPACER_LENGTH,
    MIN_RTT_3PRIME_HOMOLOGY,
    PAM,
    PBS_RANGE,
    RTT_RANGE,
    BaseEditWindow,
    Guide,
    NickingGuide,
    PegRNA,
    Spacer,
    ThreePrimeMotif,
)
from alleleforge.types.offtarget import (
    OffTargetReport,
    OffTargetSite,
    ScoreMethod,
    SiteOrigin,
)
from alleleforge.types.prediction import (
    Prediction,
    UncertaintyMethod,
    trusted_deserialization_context,
)
from alleleforge.types.provenance import (
    DatasetVersion,
    ModelCheckpoint,
    Provenance,
    ToolVersion,
)
from alleleforge.types.sequence import (
    IUPAC_ALPHABET,
    IUPAC_EXPAND,
    CoordinateSystem,
    DNASequence,
    GenomicInterval,
    Strand,
)
from alleleforge.types.variant import (
    ClinVarAccession,
    DbSnpId,
    Variant,
    VariantClass,
)

__all__ = [
    "DEFAULT_SPACER_LENGTH",
    "IUPAC_ALPHABET",
    "IUPAC_EXPAND",
    "MIN_RTT_3PRIME_HOMOLOGY",
    "PAM",
    "PBS_RANGE",
    "RTT_RANGE",
    "AlleleOutcome",
    "BaseEditWindow",
    "Chemistry",
    "ClinVarAccession",
    "CoordinateSystem",
    "DNASequence",
    "DatasetVersion",
    "DbSnpId",
    "DesignCandidate",
    "EditIntent",
    "EditOutcome",
    "EditStrategy",
    "GenomicInterval",
    "Guide",
    "ModelCheckpoint",
    "NickingGuide",
    "OffTargetReport",
    "OffTargetSite",
    "PegRNA",
    "Prediction",
    "Provenance",
    "RankedMenu",
    "ScoreMethod",
    "SiteOrigin",
    "Spacer",
    "Strand",
    "ThreePrimeMotif",
    "ToolVersion",
    "UncertaintyMethod",
    "Variant",
    "VariantClass",
    "trusted_deserialization_context",
]
