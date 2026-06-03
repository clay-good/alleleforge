"""Variant resolver (Phase 4): any input form to one canonical variant.

The front door of the variant-first journey. :func:`resolve` normalizes a
ClinVar accession, dbSNP rsID, HGVS expression, VCF record, raw coordinates, or
raw target sequence into a left-aligned, reference-validated
:class:`ResolvedVariant` with its working interval and molecular consequence.
"""

from __future__ import annotations

from alleleforge.variant.effect import (
    Consequence,
    EffectPredictor,
    Impact,
    StaticEffectPredictor,
    VariantEffect,
    VepRestPredictor,
    impact_of,
)
from alleleforge.variant.hgvs_adapter import (
    HgvsAdapter,
    HgvsOp,
    ParsedGenomicHgvs,
    parse_genomic_hgvs,
)
from alleleforge.variant.resolver import (
    RawTarget,
    ResolvedVariant,
    ResolveInput,
    VcfRecord,
    resolve,
)

__all__ = [
    "Consequence",
    "EffectPredictor",
    "HgvsAdapter",
    "HgvsOp",
    "Impact",
    "ParsedGenomicHgvs",
    "RawTarget",
    "ResolveInput",
    "ResolvedVariant",
    "StaticEffectPredictor",
    "VariantEffect",
    "VcfRecord",
    "VepRestPredictor",
    "impact_of",
    "parse_genomic_hgvs",
    "resolve",
]
