"""Normalized variant model and typed source-identifier wrappers.

A :class:`Variant` is the canonical, normalized representation every input form
(ClinVar accession, dbSNP rsID, HGVS, VCF, raw coordinates) resolves to. It
stores **0-based** coordinates internally to match the rest of AlleleForge;
human-facing layers convert at the boundary.

Normalization (left-trim shared prefixes/suffixes, parsimonious alleles) is
exposed as :meth:`Variant.normalized` and is idempotent.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

_CLINVAR_RE = re.compile(r"^(VCV|RCV|SCV)\d{9}(\.\d+)?$")
_RSID_RE = re.compile(r"^rs\d+$")
_DNA_RE = re.compile(r"^[ACGTN]*$")

#: Assembly-name synonyms collapsed to one canonical family key, so a UCSC and an
#: Ensembl/GRC name for the same assembly compare equal (``hg38`` == ``GRCh38``).
_ASSEMBLY_ALIASES: dict[str, str] = {
    "hg38": "GRCh38",
    "grch38": "GRCh38",
    "hg19": "GRCh37",
    "grch37": "GRCh37",
    "hg18": "NCBI36",
    "ncbi36": "NCBI36",
    "grch36": "NCBI36",
    "t2t-chm13v2": "CHM13v2",
    "chm13v2": "CHM13v2",
    "chm13": "CHM13v2",
    "mm39": "GRCm39",
    "grcm39": "GRCm39",
    "mm10": "GRCm38",
    "grcm38": "GRCm38",
}


def canonical_assembly(name: str) -> str:
    """Return a naming-independent key for a genome assembly name."""
    key = name.strip().lower()
    return _ASSEMBLY_ALIASES.get(key, name.strip())


def assembly_matches(a: str, b: str) -> bool:
    """Return ``True`` if two assembly names denote the same assembly."""
    return canonical_assembly(a) == canonical_assembly(b)


class VariantClass(StrEnum):
    """The structural class of a normalized variant."""

    SNV = "snv"
    MNV = "mnv"
    INSERTION = "insertion"
    DELETION = "deletion"
    INDEL = "indel"
    COMPLEX = "complex"


class ClinVarAccession(BaseModel):
    """A validated ClinVar accession (``VCV``/``RCV``/``SCV`` form)."""

    model_config = ConfigDict(frozen=True)

    value: str

    @field_validator("value")
    @classmethod
    def _validate(cls, value: str) -> str:
        """Reject anything not matching a ClinVar accession pattern."""
        upper = value.upper()
        if not _CLINVAR_RE.match(upper):
            raise ValueError(f"not a ClinVar accession: {value!r}")
        return upper

    def __str__(self) -> str:
        """Return the bare accession string."""
        return self.value


class DbSnpId(BaseModel):
    """A validated dbSNP rsID (``rs`` followed by digits)."""

    model_config = ConfigDict(frozen=True)

    value: str

    @field_validator("value")
    @classmethod
    def _validate(cls, value: str) -> str:
        """Reject anything not matching the dbSNP rsID pattern (``rs`` + digits)."""
        lower = value.lower()
        if not _RSID_RE.match(lower):
            raise ValueError(f"not a dbSNP rsID: {value!r}")
        return lower

    def __str__(self) -> str:
        """Return the bare rsID string."""
        return self.value


class Variant(BaseModel):
    """A normalized sequence variant in 0-based coordinates.

    Attributes:
        chrom: Contig / chromosome name.
        pos: 0-based start coordinate of the ``ref`` allele.
        ref: Reference allele (may be empty for a pure insertion after trimming).
        alt: Alternate allele (may be empty for a pure deletion after trimming).
        build: Reference genome build (e.g. ``"hg38"``).
        source_assembly: The native assembly a database record was parsed from
            (e.g. ``"GRCh37"``), or ``None`` when unknown / not database-sourced.
            Recorded so ``resolve`` can reconcile — not overwrite — the source
            build against the requested one.
        hgvs_g: Optional genomic HGVS string.
        hgvs_c: Optional coding HGVS string.
        hgvs_p: Optional protein HGVS string.
        clinvar: Optional source ClinVar accession.
        rsid: Optional source dbSNP rsID.
    """

    model_config = ConfigDict(frozen=True)

    chrom: str
    pos: int
    ref: str
    alt: str
    build: str = "hg38"
    source_assembly: str | None = None
    hgvs_g: str | None = None
    hgvs_c: str | None = None
    hgvs_p: str | None = None
    clinvar: ClinVarAccession | None = None
    rsid: DbSnpId | None = None

    @field_validator("ref", "alt")
    @classmethod
    def _validate_allele(cls, value: str) -> str:
        """Upper-case and restrict alleles to unambiguous bases (or empty)."""
        upper = value.upper()
        if not _DNA_RE.match(upper):
            raise ValueError(f"allele {value!r} is not an A/C/G/T/N string")
        return upper

    @field_validator("pos")
    @classmethod
    def _validate_pos(cls, value: int) -> int:
        """Reject negative coordinates."""
        if value < 0:
            raise ValueError(f"pos {value} is negative")
        return value

    @property
    def variant_class(self) -> VariantClass:
        """Classify the variant from its (already-set) alleles."""
        ref, alt = self.ref, self.alt
        if len(ref) == 1 and len(alt) == 1:
            return VariantClass.SNV
        if len(ref) == len(alt) and len(ref) > 1:
            return VariantClass.MNV
        if ref == "" and alt != "":
            return VariantClass.INSERTION
        if alt == "" and ref != "":
            return VariantClass.DELETION
        if ref and alt:
            return VariantClass.INDEL
        return VariantClass.COMPLEX

    def normalized(self) -> Variant:
        """Return a parsimonious, left-aligned copy of this variant.

        Follows anchored (bcftools-norm) semantics: trim a shared suffix base
        then a shared prefix base while *both* alleles remain longer than one
        base, advancing ``pos`` for each prefix base removed. Indels keep their
        single anchor base, so alleles never become empty. Idempotent:
        normalizing an already-normalized variant returns an equal variant.
        """
        ref, alt, pos = self.ref, self.alt, self.pos
        # Trim shared suffix (does not move pos); keep both alleles non-empty.
        while len(ref) > 1 and len(alt) > 1 and ref[-1] == alt[-1]:
            ref, alt = ref[:-1], alt[:-1]
        # Trim shared prefix (advances pos); keep both alleles non-empty.
        while len(ref) > 1 and len(alt) > 1 and ref[0] == alt[0]:
            ref, alt, pos = ref[1:], alt[1:], pos + 1
        return self.model_copy(update={"ref": ref, "alt": alt, "pos": pos})

    def __str__(self) -> str:
        """Return a compact ``chrom:pos:ref>alt`` representation."""
        return f"{self.chrom}:{self.pos}:{self.ref or '-'}>{self.alt or '-'}"
