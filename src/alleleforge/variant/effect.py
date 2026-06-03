"""Variant consequence prediction (VEP-style) for the resolver.

:class:`VariantEffect` is the structured consequence the Phase 10 router uses to
decide which chemistries are eligible for a variant (e.g. a splice-donor SNV is a
base-editing candidate; a frameshift suggests nuclease disruption). The
:class:`EffectPredictor` protocol lets the resolver consume any backend:

* :class:`StaticEffectPredictor` is a deterministic, network-free predictor used
  in tests and for pre-annotated inputs (ClinVar already carries a consequence).
* :class:`VepRestPredictor` wraps the Ensembl VEP REST API, caching responses by
  variant + transcript set. It is the production default and is never reached in
  CI (which stubs the predictor).
"""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from alleleforge.types.variant import Variant


class Consequence(StrEnum):
    """A Sequence-Ontology-style molecular consequence term."""

    TRANSCRIPT_ABLATION = "transcript_ablation"
    SPLICE_ACCEPTOR = "splice_acceptor_variant"
    SPLICE_DONOR = "splice_donor_variant"
    STOP_GAINED = "stop_gained"
    FRAMESHIFT = "frameshift_variant"
    STOP_LOST = "stop_lost"
    START_LOST = "start_lost"
    INFRAME_INSERTION = "inframe_insertion"
    INFRAME_DELETION = "inframe_deletion"
    MISSENSE = "missense_variant"
    SPLICE_REGION = "splice_region_variant"
    SYNONYMOUS = "synonymous_variant"
    FIVE_PRIME_UTR = "5_prime_UTR_variant"
    THREE_PRIME_UTR = "3_prime_UTR_variant"
    INTRON = "intron_variant"
    UPSTREAM = "upstream_gene_variant"
    DOWNSTREAM = "downstream_gene_variant"
    INTERGENIC = "intergenic_variant"
    OTHER = "other"


class Impact(IntEnum):
    """VEP impact tier (ordered so the most severe compares greatest)."""

    MODIFIER = 0
    LOW = 1
    MODERATE = 2
    HIGH = 3


#: Default impact tier for each consequence (mirrors VEP's classification).
_IMPACT: dict[Consequence, Impact] = {
    Consequence.TRANSCRIPT_ABLATION: Impact.HIGH,
    Consequence.SPLICE_ACCEPTOR: Impact.HIGH,
    Consequence.SPLICE_DONOR: Impact.HIGH,
    Consequence.STOP_GAINED: Impact.HIGH,
    Consequence.FRAMESHIFT: Impact.HIGH,
    Consequence.STOP_LOST: Impact.HIGH,
    Consequence.START_LOST: Impact.HIGH,
    Consequence.INFRAME_INSERTION: Impact.MODERATE,
    Consequence.INFRAME_DELETION: Impact.MODERATE,
    Consequence.MISSENSE: Impact.MODERATE,
    Consequence.SPLICE_REGION: Impact.LOW,
    Consequence.SYNONYMOUS: Impact.LOW,
    Consequence.FIVE_PRIME_UTR: Impact.MODIFIER,
    Consequence.THREE_PRIME_UTR: Impact.MODIFIER,
    Consequence.INTRON: Impact.MODIFIER,
    Consequence.UPSTREAM: Impact.MODIFIER,
    Consequence.DOWNSTREAM: Impact.MODIFIER,
    Consequence.INTERGENIC: Impact.MODIFIER,
    Consequence.OTHER: Impact.MODIFIER,
}


def impact_of(consequence: Consequence) -> Impact:
    """Return the default VEP impact tier for ``consequence``."""
    return _IMPACT[consequence]


class VariantEffect(BaseModel):
    """A variant's structured molecular consequence on one transcript.

    Attributes:
        consequence: The most severe Sequence-Ontology consequence term.
        impact: The VEP impact tier of ``consequence``.
        gene: The affected gene symbol, if any.
        transcript: The transcript the consequence is reported against.
        hgvs_c: Coding HGVS string, if the variant is transcribed.
        hgvs_p: Protein HGVS string, if the variant is translated.
        is_canonical: Whether ``transcript`` is the MANE Select / canonical one.
    """

    model_config = ConfigDict(frozen=True)

    consequence: Consequence
    impact: Impact
    gene: str | None = None
    transcript: str | None = None
    hgvs_c: str | None = None
    hgvs_p: str | None = None
    is_canonical: bool = True


@runtime_checkable
class EffectPredictor(Protocol):
    """Anything that maps a variant to a :class:`VariantEffect`."""

    def predict(self, variant: Variant, *, transcript: str = "MANE_SELECT") -> VariantEffect:
        """Return the consequence of ``variant`` on ``transcript``."""
        ...


class StaticEffectPredictor:
    """A deterministic, network-free predictor backed by a lookup table.

    Keys are ``str(variant)`` (``chrom:pos:ref>alt``). Unknown variants fall back
    to :attr:`Consequence.OTHER` so resolution never fails for lack of an effect.
    """

    def __init__(self, table: dict[str, VariantEffect] | None = None) -> None:
        """Initialise with an optional ``str(variant) -> VariantEffect`` table."""
        self._table = dict(table or {})

    def add(self, variant: Variant, effect: VariantEffect) -> None:
        """Register the effect of ``variant``."""
        self._table[str(variant)] = effect

    def predict(self, variant: Variant, *, transcript: str = "MANE_SELECT") -> VariantEffect:
        """Return the stored effect, or an ``OTHER``/``MODIFIER`` default."""
        return self._table.get(
            str(variant),
            VariantEffect(
                consequence=Consequence.OTHER,
                impact=Impact.MODIFIER,
                transcript=transcript,
            ),
        )


class VepRestPredictor:  # pragma: no cover - network; stubbed in CI
    """Ensembl VEP REST predictor with per-(variant, transcript) caching."""

    def __init__(self, *, server: str = "https://rest.ensembl.org") -> None:
        """Configure the VEP REST endpoint."""
        self._server = server
        self._cache: dict[tuple[str, str], VariantEffect] = {}

    def predict(self, variant: Variant, *, transcript: str = "MANE_SELECT") -> VariantEffect:
        """Return (and cache) the VEP consequence of ``variant``.

        Raises:
            RuntimeError: If the optional ``requests`` dependency is missing.
        """
        key = (str(variant), transcript)
        if key in self._cache:
            return self._cache[key]
        try:
            import requests  # noqa: F401 - optional, only on the production path
        except ImportError as exc:  # noqa: BLE001
            raise RuntimeError("VepRestPredictor requires the optional 'requests' package") from exc
        raise NotImplementedError("VEP REST querying is wired up in a later phase")
