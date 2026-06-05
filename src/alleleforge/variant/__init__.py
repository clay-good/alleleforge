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
    VepFetcher,
    VepRestPredictor,
    impact_of,
    parse_vep_response,
)
from alleleforge.variant.hgvs_adapter import (
    HgvsAdapter,
    HgvsLibraryProjector,
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
from alleleforge.variant.vcf import VcfVariantLike, iter_vcf

__all__ = [
    "Consequence",
    "EffectPredictor",
    "HgvsAdapter",
    "HgvsLibraryProjector",
    "HgvsOp",
    "Impact",
    "ParsedGenomicHgvs",
    "RawTarget",
    "ResolveInput",
    "ResolvedVariant",
    "StaticEffectPredictor",
    "VariantEffect",
    "VcfRecord",
    "VcfVariantLike",
    "VepFetcher",
    "VepRestPredictor",
    "impact_of",
    "iter_vcf",
    "parse_genomic_hgvs",
    "parse_vep_response",
    "resolve",
]
