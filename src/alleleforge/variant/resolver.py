"""The variant resolver: any input form to one canonical :class:`Variant`.

:func:`resolve` is the front door of the variant-first journey. It accepts a
ClinVar accession, a dbSNP rsID, an HGVS expression (``g.``/``c.``/``p.``), a VCF
record, raw genomic coordinates, or a raw target sequence with a marked position,
and returns a :class:`ResolvedVariant`: the normalized, **left-aligned**,
reference-validated variant plus its working interval, molecular consequence, and
any T2T reference recommendation.

Two invariants from the specification:

* **Left-aligned and parsimonious** (bcftools-norm semantics) when a reference is
  supplied, so the same biological variant from any input form normalizes to one
  canonical record.
* **Reference is validated** — an asserted ``ref`` that disagrees with the
  reference is a hard error (almost always the wrong genome build).
"""

from __future__ import annotations

import re
from typing import Protocol

from pydantic import BaseModel, ConfigDict, model_validator

from alleleforge.genome.coordinates import (
    AmbiguousRegion,
    ReferenceRecommendation,
    flag_ambiguous_regions,
)
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.sequence import CoordinateSystem, DNASequence, GenomicInterval, Strand
from alleleforge.types.variant import ClinVarAccession, DbSnpId, Variant
from alleleforge.variant.effect import EffectPredictor, VariantEffect
from alleleforge.variant.hgvs_adapter import HgvsAdapter

#: RefSeq chromosome accessions (GRCh38) -> UCSC-style contig names.
_REFSEQ_CHROM: dict[str, str] = {
    **{f"NC_0000{n:02d}": f"chr{n}" for n in range(1, 23)},
    "NC_000023": "chrX",
    "NC_000024": "chrY",
    "NC_012920": "chrM",
}

_COORD_RE = re.compile(
    r"^(?P<chrom>[\w.]+):(?P<pos>\d+):(?P<ref>[ACGTN]*)>(?P<alt>[ACGTN]*)$",
    re.IGNORECASE,
)
_RSID_RE = re.compile(r"^rs\d+$", re.IGNORECASE)
_CLINVAR_RE = re.compile(r"^(VCV|RCV|SCV)\d{9}", re.IGNORECASE)
_HGVS_RE = re.compile(r"(?:^|:)[gcpmnr]\.", re.IGNORECASE)


class _ClinVarRecordLike(Protocol):
    """The minimal shape the resolver needs from a ClinVar record."""

    variant: Variant


class ClinVarLookup(Protocol):
    """A ClinVar database the resolver can query by accession."""

    def get(self, accession: ClinVarAccession | str) -> _ClinVarRecordLike:
        """Return the record for ``accession``."""
        ...


class DbSnpLookup(Protocol):
    """A dbSNP database the resolver can query by rsID."""

    def locus(self, rsid: DbSnpId | str) -> Variant:
        """Return the variant for ``rsid``."""
        ...


class VcfRecord(BaseModel):
    """A single VCF data record (1-based ``pos``, as VCF stores it)."""

    model_config = ConfigDict(frozen=True)

    chrom: str
    pos: int
    ref: str
    alt: str
    rsid: str | None = None

    def to_variant(self) -> Variant:
        """Return the 0-based normalized :class:`Variant` for this record."""
        return Variant(
            chrom=self.chrom,
            pos=self.pos - 1,
            ref=self.ref,
            alt=self.alt,
            rsid=DbSnpId(value=self.rsid) if self.rsid else None,
        ).normalized()


class RawTarget(BaseModel):
    """A raw target sequence with a marked edit position (its own reference).

    Attributes:
        sequence: The local reference context, 5'->3' on the plus strand.
        position: 0-based offset of ``ref`` within ``sequence``.
        ref: Reference allele at ``position`` (validated against ``sequence``).
        alt: Alternate allele.
        chrom: A name for the synthetic contig the variant is placed on.
    """

    model_config = ConfigDict(frozen=True)

    sequence: DNASequence
    position: int
    ref: str
    alt: str
    chrom: str = "target"

    @model_validator(mode="after")
    def _check(self) -> RawTarget:
        """Validate the asserted ref matches the embedded sequence."""
        observed = str(self.sequence)[self.position : self.position + len(self.ref)]
        if observed.upper() != self.ref.upper():
            raise ValueError(
                f"asserted ref {self.ref!r} != sequence {observed!r} at position {self.position}"
            )
        return self

    def to_variant(self) -> Variant:
        """Return the normalized :class:`Variant` on the synthetic contig."""
        return Variant(chrom=self.chrom, pos=self.position, ref=self.ref, alt=self.alt).normalized()


#: Every accepted input form for :func:`resolve`.
ResolveInput = Variant | ClinVarAccession | DbSnpId | VcfRecord | RawTarget | str


class ResolvedVariant(BaseModel):
    """The canonical result of resolving any input form.

    Attributes:
        variant: The normalized, left-aligned, reference-validated variant.
        working_interval: The +/- ``window`` analysis interval around it.
        source: The input form it was resolved from (audit aid).
        transcript: The transcript consequence is reported against.
        effect: The molecular consequence, if an effect predictor was supplied.
        reference_recommendation: A T2T recommendation when the locus is
            hg38-ambiguous, else ``None``.
    """

    model_config = ConfigDict(frozen=True)

    variant: Variant
    working_interval: GenomicInterval
    source: str
    transcript: str = "MANE_SELECT"
    effect: VariantEffect | None = None
    reference_recommendation: ReferenceRecommendation | None = None


def _chrom_from_hgvs(reference: str | None) -> str:
    """Resolve an HGVS reference prefix to a contig name.

    Raises:
        ValueError: If the prefix is missing or an unmapped RefSeq accession.
    """
    if reference is None:
        raise ValueError("genomic HGVS needs a contig prefix (e.g. 'chr2:g...')")
    if reference.lower().startswith("chr"):
        return reference
    key = reference.split(".")[0]
    if key in _REFSEQ_CHROM:
        return _REFSEQ_CHROM[key]
    raise ValueError(f"cannot map HGVS reference {reference!r} to a contig")


def _from_string(
    text: str,
    *,
    clinvar: ClinVarLookup | None,
    dbsnp: DbSnpLookup | None,
    hgvs: HgvsAdapter | None,
    reference: ReferenceGenome | None,
) -> tuple[Variant, str]:
    """Dispatch a string input to its variant + a source label."""
    text = text.strip()
    if _RSID_RE.match(text):
        return _from_dbsnp(DbSnpId(value=text), dbsnp), "rsid"
    if _CLINVAR_RE.match(text):
        return _from_clinvar(ClinVarAccession(value=text), clinvar), "clinvar"
    if _HGVS_RE.search(text):
        return _from_hgvs(text, hgvs, reference), "hgvs"
    m = _COORD_RE.match(text)
    if m is None:
        raise ValueError(f"unrecognized variant input: {text!r}")
    return (
        Variant(
            chrom=m.group("chrom"),
            pos=int(m.group("pos")) - 1,  # human-facing coordinate strings are 1-based
            ref=m.group("ref").upper(),
            alt=m.group("alt").upper(),
        ).normalized(),
        "coordinates",
    )


def _from_clinvar(accession: ClinVarAccession, clinvar: ClinVarLookup | None) -> Variant:
    """Look up a ClinVar accession (requires a ClinVar DB)."""
    if clinvar is None:
        raise ValueError("resolving a ClinVar accession requires a clinvar= database")
    return clinvar.get(accession).variant


def _from_dbsnp(rsid: DbSnpId, dbsnp: DbSnpLookup | None) -> Variant:
    """Look up a dbSNP rsID (requires a dbSNP DB)."""
    if dbsnp is None:
        raise ValueError("resolving a dbSNP rsID requires a dbsnp= database")
    return dbsnp.locus(rsid)


def _from_hgvs(text: str, hgvs: HgvsAdapter | None, reference: ReferenceGenome | None) -> Variant:
    """Resolve an HGVS expression to a variant (genomic natively)."""
    adapter = hgvs or HgvsAdapter()
    chrom: str | None = None
    if adapter.is_genomic(text):
        from alleleforge.variant.hgvs_adapter import parse_genomic_hgvs

        chrom = _chrom_from_hgvs(parse_genomic_hgvs(text).reference)
    lookup = None
    if reference is not None:
        captured = chrom

        def lookup(start: int, end: int, _chrom: str | None = captured) -> str:
            assert _chrom is not None
            return str(
                reference.fetch(
                    GenomicInterval(chrom=_chrom, start=start, end=end, strand=Strand.PLUS)
                )
            )

    if chrom is None:
        # A c./p. expression: project first, then read its contig prefix.
        from alleleforge.variant.hgvs_adapter import parse_genomic_hgvs

        projected = adapter._project(text)  # noqa: SLF001 - same package
        chrom = _chrom_from_hgvs(parse_genomic_hgvs(projected).reference)
    return adapter.to_variant(text, chrom=chrom, ref_lookup=lookup)


def _to_variant(
    inp: ResolveInput,
    *,
    clinvar: ClinVarLookup | None,
    dbsnp: DbSnpLookup | None,
    hgvs: HgvsAdapter | None,
    reference: ReferenceGenome | None,
) -> tuple[Variant, str]:
    """Convert any accepted input form to a (variant, source) pair."""
    if isinstance(inp, Variant):
        return inp.normalized(), "variant"
    if isinstance(inp, ClinVarAccession):
        return _from_clinvar(inp, clinvar), "clinvar"
    if isinstance(inp, DbSnpId):
        return _from_dbsnp(inp, dbsnp), "rsid"
    if isinstance(inp, VcfRecord):
        return inp.to_variant(), "vcf"
    if isinstance(inp, RawTarget):
        return inp.to_variant(), "raw_sequence"
    return _from_string(inp, clinvar=clinvar, dbsnp=dbsnp, hgvs=hgvs, reference=reference)


def _ref_base(reference: ReferenceGenome, chrom: str, pos: int) -> str:
    """Return the single plus-strand reference base at 0-based ``pos``."""
    return str(
        reference.fetch(GenomicInterval(chrom=chrom, start=pos, end=pos + 1, strand=Strand.PLUS))
    )


def _left_align(variant: Variant, reference: ReferenceGenome) -> Variant:
    """Left-align and parsimoniously trim an indel against the reference.

    Substitutions and MNVs are returned unchanged. Pure indels are reduced to
    their minimal (anchor-free) representation, rolled as far left as the
    reference repeat structure allows, then re-anchored on the preceding base.
    """
    v = variant.normalized()
    ref, alt, pos = v.ref, v.alt, v.pos
    if len(ref) == len(alt):
        return v  # SNV / MNV: nothing to roll
    # Validate the caller's asserted anchor/flanking base BEFORE re-anchoring. The
    # re-anchor step below re-reads the anchor from the reference, which would
    # overwrite (and so silently accept) a wrong-build insertion whose asserted
    # anchor disagrees — defeating the fail-closed guarantee precisely for
    # insertions. Checking the original assertion first is what closes that hole.
    _validate_ref(v, reference)
    while ref and alt and ref[-1] == alt[-1]:  # strip shared suffix to minimal form
        ref, alt = ref[:-1], alt[:-1]
    while ref and alt and ref[0] == alt[0]:  # strip shared prefix
        ref, alt, pos = ref[1:], alt[1:], pos + 1
    while pos > 0:  # roll the indel left through a repeat
        indel = ref if alt == "" else alt
        prev = _ref_base(reference, v.chrom, pos - 1)
        if indel and prev == indel[-1]:
            rolled = prev + indel[:-1]
            ref, alt = (rolled, "") if alt == "" else ("", rolled)
            pos -= 1
        else:
            break
    if pos > 0 and (ref == "" or alt == ""):  # re-anchor on the preceding base
        anchor = _ref_base(reference, v.chrom, pos - 1)
        ref, alt, pos = anchor + ref, anchor + alt, pos - 1
    return v.model_copy(update={"ref": ref, "alt": alt, "pos": pos})


def _validate_ref(variant: Variant, reference: ReferenceGenome) -> None:
    """Raise if the variant's asserted ref disagrees with the reference.

    Raises:
        ValueError: On a ref/reference mismatch (likely the wrong build).
    """
    if not variant.ref:
        return
    result = reference.fetch_result(
        GenomicInterval(
            chrom=variant.chrom,
            start=variant.pos,
            end=variant.pos + len(variant.ref),
            strand=Strand.PLUS,
        )
    )
    observed = str(result.sequence)
    if result.padded or observed != variant.ref:
        raise ValueError(
            f"reference mismatch at {variant.chrom}:{variant.pos}: asserted ref "
            f"{variant.ref!r} but reference has {observed!r} (wrong build?)"
        )


def _working_interval(
    variant: Variant, window: int, reference: ReferenceGenome | None
) -> GenomicInterval:
    """Return the +/- ``window`` analysis interval around ``variant``."""
    start = max(0, variant.pos - window)
    end = variant.pos + max(1, len(variant.ref)) + window
    if reference is not None and variant.chrom in reference.contigs:
        end = min(end, reference.contig_length(variant.chrom))
    return GenomicInterval(
        chrom=variant.chrom,
        start=start,
        end=end,
        strand=Strand.PLUS,
        coordinate_system=CoordinateSystem.ZERO_BASED_HALF_OPEN,
    )


def resolve(
    inp: ResolveInput,
    *,
    build: str = "hg38",
    window: int = 100,
    transcript: str = "MANE_SELECT",
    reference: ReferenceGenome | None = None,
    clinvar: ClinVarLookup | None = None,
    dbsnp: DbSnpLookup | None = None,
    hgvs: HgvsAdapter | None = None,
    effect: EffectPredictor | None = None,
    ambiguous_regions: tuple[AmbiguousRegion, ...] | None = None,
) -> ResolvedVariant:
    """Resolve any input form to a canonical :class:`ResolvedVariant`.

    Args:
        inp: A ClinVar accession, dbSNP rsID, HGVS string, :class:`VcfRecord`,
            :class:`RawTarget`, raw ``chrom:pos:ref>alt`` string, or a
            :class:`Variant`.
        build: The reference build the input is expressed in.
        window: Half-width (bp) of the working interval around the variant.
        transcript: Transcript model for consequence calling (MANE Select).
        reference: A :class:`ReferenceGenome` for left-alignment and ref
            validation; when omitted those steps are skipped.
        clinvar: A ClinVar database (needed for accession inputs).
        dbsnp: A dbSNP database (needed for rsID inputs).
        hgvs: An :class:`HgvsAdapter` (needed for ``c.``/``p.`` inputs).
        effect: An :class:`EffectPredictor` to annotate the consequence.
        ambiguous_regions: Override table for hg38-ambiguous-region flagging.

    Returns:
        The canonical :class:`ResolvedVariant`.

    Raises:
        ValueError: On an unrecognized input, a missing required database, or a
            reference mismatch.
    """
    variant, source = _to_variant(inp, clinvar=clinvar, dbsnp=dbsnp, hgvs=hgvs, reference=reference)
    variant = variant.model_copy(update={"build": build})
    if reference is not None:
        variant = _left_align(variant, reference)
        _validate_ref(variant, reference)
    else:
        variant = variant.normalized()

    working = _working_interval(variant, window, reference)
    recommendation = flag_ambiguous_regions(working, source_build=build, regions=ambiguous_regions)
    return ResolvedVariant(
        variant=variant,
        working_interval=working,
        source=source,
        transcript=transcript,
        effect=effect.predict(variant, transcript=transcript) if effect is not None else None,
        reference_recommendation=recommendation if recommendation.recommended else None,
    )
