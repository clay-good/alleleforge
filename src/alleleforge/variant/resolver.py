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
from alleleforge.types.sequence import (
    CoordinateSystem,
    DNASequence,
    GenomicInterval,
    Strand,
    canonical_contig,
)
from alleleforge.types.variant import (
    ClinicalAssertion,
    ClinVarAccession,
    DbSnpId,
    Variant,
    assembly_matches,
)
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


#: What a dispatcher returns: the variant, the input form it came from, and whatever a
#: clinical database asserted about it (``None`` for every non-database form).
_Resolution = tuple[Variant, str, "ClinicalAssertion | None"]


class _ClinVarRecordLike(Protocol):
    """The minimal shape the resolver needs from a ClinVar record.

    Only ``variant`` is required. A real :class:`~alleleforge.data.clinvar.ClinVarRecord`
    also carries the classification, which :func:`_clinical_assertion` reads when
    present — the resolver stays usable with a bare coordinate stub (as tests supply)
    while a full record contributes what the user actually chose the accession for.
    """

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
        """Return the 0-based :class:`Variant` for this record (un-normalized).

        Normalization is deferred to :func:`resolve` so it can validate the *full*
        asserted ref span against the reference first — trimming a shared prefix/
        suffix base here would discard a wrong-build base before it is ever checked.
        """
        return Variant(
            chrom=self.chrom,
            pos=self.pos - 1,
            ref=self.ref,
            alt=self.alt,
            rsid=DbSnpId(value=self.rsid) if self.rsid else None,
        )


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
        clinical_assertion: What a clinical database asserts about this variant, when
            resolution came from one. A ClinVar accession is chosen for its
            classification, not its coordinates; carrying only the coordinates left
            every downstream layer unable to say whether it was correcting a
            pathogenic allele or a benign one.
        transcript: The transcript consequence is reported against.
        effect: The molecular consequence, if an effect predictor was supplied.
        reference_recommendation: A T2T recommendation when the locus is
            hg38-ambiguous, else ``None``.
    """

    model_config = ConfigDict(frozen=True)

    variant: Variant
    working_interval: GenomicInterval
    source: str
    clinical_assertion: ClinicalAssertion | None = None
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
) -> _Resolution:
    """Dispatch a string input to its variant + source label + any assertion."""
    text = text.strip()
    if _RSID_RE.match(text):
        return _from_dbsnp(DbSnpId(value=text), dbsnp), "rsid", None
    if _CLINVAR_RE.match(text):
        variant, assertion = _from_clinvar(ClinVarAccession(value=text), clinvar)
        return variant, "clinvar", assertion
    if _HGVS_RE.search(text):
        return _from_hgvs(text, hgvs, reference), "hgvs", None
    m = _COORD_RE.match(text)
    if m is None:
        raise ValueError(f"unrecognized variant input: {text!r}")
    return (
        # Un-normalized on purpose: resolve() validates the full asserted ref span
        # against the reference before parsimony trims a shared prefix/suffix base
        # (which could carry a wrong-build mismatch — see _to_variant / resolve).
        Variant(
            chrom=m.group("chrom"),
            pos=int(m.group("pos")) - 1,  # human-facing coordinate strings are 1-based
            ref=m.group("ref").upper(),
            alt=m.group("alt").upper(),
        ),
        "coordinates",
        None,
    )


def _clinical_assertion(record: _ClinVarRecordLike) -> ClinicalAssertion | None:
    """Return the record's classification, if it carries one.

    Read defensively rather than through the Protocol: the resolver's contract with a
    ClinVar database is deliberately minimal (a coordinate stub is a valid lookup), and
    requiring the classification would break every such stub to gain nothing — a record
    without one simply asserts nothing.
    """
    significance = getattr(record, "significance", None)
    if significance is None:
        return None
    return ClinicalAssertion(
        significance=significance,
        review_status=getattr(record, "review_status", None),
        raw=getattr(record, "raw_significance", None),
    )


def _from_clinvar(
    accession: ClinVarAccession, clinvar: ClinVarLookup | None
) -> tuple[Variant, ClinicalAssertion | None]:
    """Look up a ClinVar accession (requires a ClinVar DB).

    Returns the variant **and** what ClinVar asserts about it. Returning only the
    variant discarded the classification the user chose the accession for, so a design
    could not say whether it was correcting a pathogenic allele or a benign one.
    """
    if clinvar is None:
        raise ValueError("resolving a ClinVar accession requires a clinvar= database")
    record = clinvar.get(accession)
    return record.variant, _clinical_assertion(record)


def _from_dbsnp(rsid: DbSnpId, dbsnp: DbSnpLookup | None) -> Variant:
    """Look up a dbSNP rsID (requires a dbSNP DB)."""
    if dbsnp is None:
        raise ValueError("resolving a dbSNP rsID requires a dbsnp= database")
    return dbsnp.locus(rsid)


def _from_hgvs(text: str, hgvs: HgvsAdapter | None, reference: ReferenceGenome | None) -> Variant:
    """Resolve an HGVS expression to a variant (genomic natively)."""
    adapter = hgvs or HgvsAdapter()
    from alleleforge.variant.hgvs_adapter import parse_genomic_hgvs

    if adapter.is_genomic(text):
        chrom = _chrom_from_hgvs(parse_genomic_hgvs(text).reference)
    else:
        # A c./p. expression: project first, then read its contig prefix.
        projected = adapter._project(text)  # noqa: SLF001 - same package
        chrom = _chrom_from_hgvs(parse_genomic_hgvs(projected).reference)
    # Define the reference accessor only after ``chrom`` is resolved: a c./p. input
    # does not know its contig until the projection above, and a closure that
    # snapshotted the pre-projection ``None`` would crash any coding
    # deletion/dup/delins whose projector omits the reference bases.
    lookup = None
    if reference is not None:

        def lookup(start: int, end: int, _chrom: str = chrom) -> str:
            return str(
                reference.fetch(
                    GenomicInterval(chrom=_chrom, start=start, end=end, strand=Strand.PLUS)
                )
            )

    return adapter.to_variant(text, chrom=chrom, ref_lookup=lookup)


def _to_variant(
    inp: ResolveInput,
    *,
    clinvar: ClinVarLookup | None,
    dbsnp: DbSnpLookup | None,
    hgvs: HgvsAdapter | None,
    reference: ReferenceGenome | None,
) -> _Resolution:
    """Convert any accepted input form to a (variant, source, assertion) triple.

    Coordinate-family inputs (a raw :class:`Variant`, a :class:`VcfRecord`, or a
    ``chrom:pos:ref>alt`` string) are returned **un-normalized** so :func:`resolve`
    can validate their full asserted ref span against the reference before parsimony
    trims a shared prefix/suffix base — otherwise a wrong-build base hidden in that
    trimmed base is silently laundered instead of failing closed. The database/HGVS
    forms validate their asserted bases before this point (RawTarget against its
    embedded sequence, HGVS against the stated ref), so they are already safe.
    """
    if isinstance(inp, Variant):
        return inp, "variant", None
    if isinstance(inp, ClinVarAccession):
        variant, assertion = _from_clinvar(inp, clinvar)
        return variant, "clinvar", assertion
    if isinstance(inp, DbSnpId):
        return _from_dbsnp(inp, dbsnp), "rsid", None
    if isinstance(inp, VcfRecord):
        return inp.to_variant(), "vcf", None
    if isinstance(inp, RawTarget):
        return inp.to_variant(), "raw_sequence", None
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
    if ref and alt:
        # A true delins (both alleles non-empty after minimal trimming) is not a
        # pure indel: it has no single anchor base to roll and no repeat to roll
        # into. The rolling loop below assumes exactly one allele is empty, so
        # letting a delins fall through would drop its deleted bases entirely.
        return v.model_copy(update={"ref": ref, "alt": alt, "pos": pos})
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
    if reference is not None:
        # Clamp through the naming-reconciling accessor, not raw `contigs`
        # membership: a `chr`-named variant against an Ensembl-named reference (the
        # common ClinVar/dbSNP-vs-built-in-hg38 path) is present under its aliased
        # name, so `contig_length` resolves it while `variant.chrom in contigs`
        # would be False and silently skip the clamp, leaking an off-contig end.
        try:
            end = min(end, reference.contig_length(variant.chrom))
        except KeyError:  # genuinely absent (incl. unresolvable naming mismatch)
            pass
    return GenomicInterval(
        chrom=variant.chrom,
        start=start,
        end=end,
        strand=Strand.PLUS,
        coordinate_system=CoordinateSystem.ZERO_BASED_HALF_OPEN,
    )


def _rename_contig_to_reference(variant: Variant, reference: ReferenceGenome) -> Variant:
    """Return ``variant`` with its contig spelled as ``reference`` spells it.

    Only the name changes, and only when the reference has a contig that reconciles
    to the same canonical form. An unknown contig is left alone so the existing
    reference-base validation raises the error it already raises, rather than this
    quietly renaming a variant onto the wrong sequence.

    Args:
        variant: The variant as the caller spelled it.
        reference: The genome it is being resolved against.

    Returns:
        The variant, renamed when the reference knows the contig by another spelling.
    """
    canonical = canonical_contig(variant.chrom)
    for contig in reference.contigs:
        if canonical_contig(contig) == canonical:
            return (
                variant if contig == variant.chrom else variant.model_copy(update={"chrom": contig})
            )
    return variant


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
    variant, source, assertion = _to_variant(
        inp, clinvar=clinvar, dbsnp=dbsnp, hgvs=hgvs, reference=reference
    )
    # Reconcile — never silently overwrite — a database record's native assembly.
    # A source record that states its assembly must agree with the requested build
    # (no liftover happens here); otherwise the mislabel would poison provenance,
    # the working interval, and the VEP assembly selection downstream.
    if variant.source_assembly is not None and not assembly_matches(variant.source_assembly, build):
        raise ValueError(
            f"source assembly {variant.source_assembly!r} disagrees with requested build "
            f"{build!r}; lift the coordinates to {build!r} before resolving rather than "
            f"relabeling them — `aforge lift <locus> --chain <file> --from "
            f"{variant.source_assembly} --to {build}`"
        )
    variant = variant.model_copy(update={"build": build})
    if reference is not None:
        # A resolved variant is a position *in this reference*, so it is named the way
        # this reference names it. Contig-style reconciliation already makes the lookup
        # work either way; what it did not do is settle what gets written down, so a
        # `2:71:A>C` input against a `chr2` genome produced a candidate locus of
        # `2:43-63` while the off-target sites found in the same genome said `chr2:…`.
        # The rename is always toward the supplied genome: a bare-named FASTA keeps
        # bare-named output.
        variant = _rename_contig_to_reference(variant, reference)
        # Validate the FULL asserted ref span *before* normalization. `normalized()`
        # (applied inside `_left_align`, and in the no-reference branch below) trims a
        # shared prefix/suffix base whenever ref==alt there — so a wrong-build base in
        # that trimmed position (e.g. asserted `AT>GT` where the reference is `AC`; the
        # unchanged `T` is trimmed to leave `A>G`, which validates) would be laundered
        # away, silently accepting a wrong build and changing the caller's edit. The
        # post-normalization check below only sees the trimmed ref, so this earlier
        # full-span check on the raw assertion is what actually closes the hole.
        _validate_ref(variant, reference)
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
        clinical_assertion=assertion,
        transcript=transcript,
        effect=effect.predict(variant, transcript=transcript) if effect is not None else None,
        reference_recommendation=recommendation if recommendation.recommended else None,
    )
