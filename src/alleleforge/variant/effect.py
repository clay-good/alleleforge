"""Variant consequence prediction (VEP-style) for the resolver.

:class:`VariantEffect` is the structured consequence the Phase 10 router uses to
decide which chemistries are eligible for a variant (e.g. a splice-donor SNV is a
base-editing candidate; a frameshift suggests nuclease disruption). The
:class:`EffectPredictor` protocol lets the resolver consume any backend:

* :class:`StaticEffectPredictor` is a deterministic, network-free predictor used
  in tests and for pre-annotated inputs (ClinVar already carries a consequence).
* :class:`VepRestPredictor` wraps the Ensembl VEP REST API, caching responses by
  ``(variant, assembly, transcript)``. Its HTTP fetch is injectable, so the
  response parsing (:func:`parse_vep_response`) is exercised in CI against a
  recorded fixture; only the live GET (the default fetcher) is never run in CI.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import IntEnum, StrEnum
from typing import Any, Protocol, runtime_checkable

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


#: Total Sequence-Ontology severity order, most severe first. The ``Consequence``
#: enum is declared in VEP's severity order, so its member order *is* the rank. Used
#: to pick the single most-severe term when a transcript lists several: ``impact_of``
#: is only a coarse 4-bucket tier, so a tie within a tier (e.g. splice_region vs
#: synonymous, or frameshift vs splice_donor) would otherwise fall to VEP's
#: term-list order, which is not severity-sorted.
_SEVERITY_RANK: dict[Consequence, int] = {
    c: rank for rank, c in enumerate(reversed(tuple(Consequence)))
}


def _severity(consequence: Consequence) -> int:
    """Return a total severity rank (higher = more severe) for tie-breaking."""
    return _SEVERITY_RANK[consequence]


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


#: A VEP fetcher takes a request URL and returns the parsed JSON array Ensembl
#: returns for it. Injected so tests replay a recorded response with no network;
#: the default implementation issues the real GET via the optional ``requests``.
VepFetcher = Callable[[str], list[dict[str, Any]]]


def _assembly_of(variant: Variant) -> str:
    """Return the GRCh assembly name VEP expects for ``variant``'s build."""
    build = (variant.build or "").lower()
    if build in {"hg38", "grch38"}:
        return "GRCh38"
    if build in {"hg19", "grch37"}:
        return "GRCh37"
    return variant.build or "GRCh38"


def parse_vep_response(
    payload: list[dict[str, Any]], *, transcript: str = "MANE_SELECT"
) -> VariantEffect:
    """Parse an Ensembl VEP REST response into a :class:`VariantEffect`.

    Picks the transcript consequence to report: the MANE Select / canonical one
    for the default ``transcript="MANE_SELECT"``, an exact ``transcript_id`` match
    when a specific transcript is named, else the first listed. The reported
    consequence is the most severe Sequence-Ontology term on that transcript;
    unknown terms degrade to :attr:`Consequence.OTHER`.

    Args:
        payload: The decoded JSON array VEP returns (one element per input).
        transcript: ``"MANE_SELECT"`` (default), or a specific transcript id.

    Returns:
        The structured consequence; an ``INTERGENIC``/``MODIFIER`` default when
        the response carries no transcript consequences.
    """
    if not payload:
        return VariantEffect(consequence=Consequence.INTERGENIC, impact=Impact.MODIFIER)
    record = payload[0]
    cons = record.get("transcript_consequences") or []
    if not cons:
        term = record.get("most_severe_consequence", Consequence.INTERGENIC.value)
        consequence = _term_to_consequence(term)
        return VariantEffect(consequence=consequence, impact=impact_of(consequence))

    chosen = _select_transcript(cons, transcript)
    terms = chosen.get("consequence_terms") or [record.get("most_severe_consequence", "other")]
    # Pick the single most-severe SO term by the total severity rank, not the
    # coarse impact tier: within one tier `max(key=impact_of)` would tie and fall
    # to VEP's (unsorted) term order, e.g. picking synonymous over splice_region or
    # frameshift over splice_donor — the latter mis-routes the editing chemistry.
    consequence = max((_term_to_consequence(t) for t in terms), key=_severity)
    impact = _IMPACT_NAMES.get(str(chosen.get("impact", "")).upper(), impact_of(consequence))
    return VariantEffect(
        consequence=consequence,
        impact=impact,
        gene=chosen.get("gene_symbol"),
        transcript=chosen.get("transcript_id"),
        hgvs_c=chosen.get("hgvsc"),
        hgvs_p=chosen.get("hgvsp"),
        is_canonical=bool(chosen.get("canonical") or chosen.get("mane_select")),
    )


def _term_to_consequence(term: str) -> Consequence:
    """Map a Sequence-Ontology term to a :class:`Consequence` (``OTHER`` if new)."""
    try:
        return Consequence(term)
    except ValueError:
        return Consequence.OTHER


#: VEP impact strings → the ordered :class:`Impact` tier.
_IMPACT_NAMES = {i.name: i for i in Impact}


def _select_transcript(consequences: list[dict[str, Any]], transcript: str) -> dict[str, Any]:
    """Return the transcript consequence block to report on.

    For a named ``transcript`` an exact ``transcript_id`` match wins. Otherwise
    (the default ``"MANE_SELECT"``) the **MANE Select** transcript is preferred,
    then any **canonical** one, then the first block — in that strict priority,
    because VEP does not guarantee MANE-first ordering, so a single pass keying on
    "MANE *or* canonical" would return a merely-canonical transcript that happened
    to precede the MANE Select one. Membership is tested by truthiness (a MANE
    accession / ``canonical: 1``), so an explicit falsy value never matches.
    """
    if transcript != "MANE_SELECT":
        for c in consequences:
            if c.get("transcript_id") == transcript:
                return c
    for c in consequences:  # 1. the MANE Select transcript
        if c.get("mane_select"):
            return c
    for c in consequences:  # 2. failing that, any canonical transcript
        if c.get("canonical"):
            return c
    return consequences[0]  # 3. else the first reported block


class VepRestPredictor:
    """Ensembl VEP REST predictor with per-(variant, assembly, transcript) caching.

    The HTTP fetch is injectable so CI replays a recorded response; the default
    fetcher issues a real GET against the VEP region endpoint via the optional
    ``requests`` package.
    """

    def __init__(
        self, *, server: str = "https://rest.ensembl.org", fetcher: VepFetcher | None = None
    ) -> None:
        """Configure the VEP REST endpoint and (optionally) an injected fetcher."""
        self._server = server
        self._fetcher = fetcher
        self._cache: dict[tuple[str, str, str], VariantEffect] = {}

    def request_url(self, variant: Variant) -> str:
        """Return the VEP region-endpoint URL for ``variant``.

        For an insertion (empty ``ref``) VEP's region convention is ``start = end + 1``
        (a zero-width span between two bases), so ``end`` is ``start - 1``. Clamping the
        span to a minimum width of 1 would send a 1-base region VEP reads as a
        substitution that consumes the base at ``start`` — a consequence for the wrong
        span. ``end = start + len(ref) - 1`` gives the correct region for every class:
        SNV → ``start``, deletion/MNV → ``start + len(ref) - 1``, insertion → ``start - 1``.
        """
        start = variant.pos + 1  # VEP regions are 1-based
        end = start + len(variant.ref) - 1
        region = f"{variant.chrom}:{start}-{end}"
        return (
            f"{self._server}/vep/{_assembly_of(variant).lower()}/region/"
            f"{region}/{variant.alt or '-'}?content-type=application/json"
        )

    def predict(self, variant: Variant, *, transcript: str = "MANE_SELECT") -> VariantEffect:
        """Return (and cache) the VEP consequence of ``variant``.

        Raises:
            RuntimeError: If no fetcher was injected and the optional ``requests``
                dependency is missing.
        """
        key = (str(variant), _assembly_of(variant), transcript)
        if key in self._cache:
            return self._cache[key]
        payload = (self._fetcher or self._default_fetch)(self.request_url(variant))
        effect = parse_vep_response(payload, transcript=transcript)
        self._cache[key] = effect
        return effect

    def _default_fetch(self, url: str) -> list[dict[str, Any]]:  # pragma: no cover - network
        """Issue the real VEP GET via ``requests`` (never run in CI)."""
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("VepRestPredictor requires the optional 'requests' package") from exc
        response = requests.get(url, headers={"Accept": "application/json"}, timeout=30)
        response.raise_for_status()
        data: list[dict[str, Any]] = response.json()
        return data
