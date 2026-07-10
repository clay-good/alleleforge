"""ClinVar access: parse a ClinVar release into normalized :class:`Variant`s.

The monthly ClinVar VCF release is parsed into :class:`ClinVarRecord`s, each
pairing a normalized :class:`~alleleforge.types.variant.Variant` with its
clinical significance, review status, gene, and source rsID. The VCF ``ID``
column is the ClinVar VariationID; the ``VCV`` accession is reconstructed from it
(VariationID 12 -> ``VCV000000012``), matching ClinVar's accession scheme.

Parsing is pure Python over a plain-text (optionally gzipped) VCF so the test
suite needs no ``cyvcf2``/``pysam`` and never opens a multi-gigabyte release;
production callers fetch the pinned release through the Phase 3 registry.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from alleleforge.data._io import is_sequence_allele, open_text
from alleleforge.types.sequence import GenomicInterval, canonical_contig
from alleleforge.types.variant import ClinVarAccession, DbSnpId, Variant


class ClinicalSignificance(StrEnum):
    """The normalized ACMG-style clinical significance classes."""

    PATHOGENIC = "pathogenic"
    LIKELY_PATHOGENIC = "likely_pathogenic"
    UNCERTAIN = "uncertain_significance"
    LIKELY_BENIGN = "likely_benign"
    BENIGN = "benign"
    CONFLICTING = "conflicting"
    OTHER = "other"
    NOT_PROVIDED = "not_provided"


#: Map raw ClinVar ``CLNSIG`` tokens to a normalized significance class.
_CLNSIG_MAP: dict[str, ClinicalSignificance] = {
    "pathogenic": ClinicalSignificance.PATHOGENIC,
    "pathogenic/likely_pathogenic": ClinicalSignificance.PATHOGENIC,
    "likely_pathogenic": ClinicalSignificance.LIKELY_PATHOGENIC,
    "uncertain_significance": ClinicalSignificance.UNCERTAIN,
    "likely_benign": ClinicalSignificance.LIKELY_BENIGN,
    "benign/likely_benign": ClinicalSignificance.BENIGN,
    "benign": ClinicalSignificance.BENIGN,
    "conflicting_classifications_of_pathogenicity": ClinicalSignificance.CONFLICTING,
    "conflicting_interpretations_of_pathogenicity": ClinicalSignificance.CONFLICTING,
    "not_provided": ClinicalSignificance.NOT_PROVIDED,
}


def _normalize_significance(raw: str | None) -> ClinicalSignificance:
    """Map a raw ``CLNSIG`` value to a :class:`ClinicalSignificance`.

    ClinVar appends secondary assertions to the primary clinical class in a single
    comma-joined ``CLNSIG`` token (e.g. ``Pathogenic,_risk_factor``,
    ``Likely_pathogenic,_low_penetrance``). Classify by the primary assertion — the
    token before the first comma — so a pathogenic call carrying a secondary
    modifier is not collapsed to ``OTHER``.
    """
    if not raw:
        return ClinicalSignificance.NOT_PROVIDED
    token = raw.strip().lower()
    if token in _CLNSIG_MAP:
        return _CLNSIG_MAP[token]
    primary = token.split(",", 1)[0]
    return _CLNSIG_MAP.get(primary, ClinicalSignificance.OTHER)


def accession_from_variation_id(variation_id: str | int) -> ClinVarAccession:
    """Return the ``VCV`` accession for a ClinVar VariationID."""
    return ClinVarAccession(value=f"VCV{int(variation_id):09d}")


class ClinVarRecord(BaseModel):
    """A ClinVar variant with its clinical annotation.

    Attributes:
        variant: The normalized variant (0-based, with accession + rsID attached).
        accession: The reconstructed ``VCV`` accession.
        significance: Normalized clinical significance.
        review_status: The raw ClinVar review-status string (star rating source).
        gene: Gene symbol from ``GENEINFO``, if present.
        raw_significance: The verbatim ``CLNSIG`` token, for auditing.
    """

    model_config = ConfigDict(frozen=True)

    variant: Variant
    accession: ClinVarAccession
    significance: ClinicalSignificance
    review_status: str | None = None
    gene: str | None = None
    raw_significance: str | None = None


def _parse_info(field: str) -> dict[str, str]:
    """Parse a VCF ``INFO`` column into a flag/value dict."""
    info: dict[str, str] = {}
    if field == ".":
        return info
    for part in field.split(";"):
        if "=" in part:
            key, _, value = part.partition("=")
            info[key] = value
        else:
            info[part] = ""
    return info


class ClinVarDB:
    """Indexed, queryable access to a parsed ClinVar release."""

    def __init__(self, records: Iterable[ClinVarRecord]) -> None:
        """Build lookup indices over ``records`` (by accession, rsID, gene)."""
        self._records: list[ClinVarRecord] = list(records)
        self._by_accession: dict[str, ClinVarRecord] = {}
        self._by_rsid: dict[str, list[ClinVarRecord]] = defaultdict(list)
        self._by_gene: dict[str, list[ClinVarRecord]] = defaultdict(list)
        for rec in self._records:
            self._by_accession[rec.accession.value] = rec
            if rec.variant.rsid is not None:
                self._by_rsid[rec.variant.rsid.value].append(rec)
            if rec.gene is not None:
                self._by_gene[rec.gene.upper()].append(rec)

    @classmethod
    def from_vcf(
        cls, path: str | Path, *, add_chr_prefix: bool = True, assembly: str | None = None
    ) -> ClinVarDB:
        """Parse a ClinVar VCF (plain or ``.gz``) into a :class:`ClinVarDB`.

        Args:
            path: Path to the ClinVar VCF release.
            add_chr_prefix: Prepend ``chr`` to bare numeric/``X``/``Y``/``MT``
                contig names so coordinates match the hg38 reference convention.
            assembly: The release's native assembly (e.g. ``"GRCh37"``). When
                omitted it is sniffed from the VCF header (ClinVar states it in a
                ``##reference`` / ``##fileformat`` line); if the header does not
                state it, each record's ``source_assembly`` is left unknown rather
                than assuming the default build.

        Returns:
            A queryable :class:`ClinVarDB`.
        """
        return cls(cls._parse(path, add_chr_prefix=add_chr_prefix, assembly=assembly))

    @staticmethod
    def _parse(
        path: str | Path, *, add_chr_prefix: bool, assembly: str | None = None
    ) -> Iterator[ClinVarRecord]:
        """Yield one :class:`ClinVarRecord` per usable VCF data line."""
        source_assembly = assembly
        for line in open_text(path):
            if line.startswith("#") or not line.strip():
                if source_assembly is None and line.startswith("#"):
                    source_assembly = _sniff_assembly(line)
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 8:
                continue
            chrom, pos_s, vid, ref, alt = cols[0], cols[1], cols[2], cols[3], cols[4]
            # ClinVar includes ref-only / structural / spanning-deletion rows whose ALT
            # is not literal sequence (`.`, `*`, `<DEL>`). Skip them rather than letting
            # one reach the allele validator and abort the whole release.
            if alt in (".", "") or not is_sequence_allele(ref if ref != "." else "", alt):
                continue
            info = _parse_info(cols[7])
            chrom_norm = _with_chr(chrom) if add_chr_prefix else chrom
            rsid = DbSnpId(value=f"rs{info['RS']}") if info.get("RS") else None
            gene = info["GENEINFO"].split(":")[0] if info.get("GENEINFO") else None
            accession = accession_from_variation_id(vid)
            variant = Variant(
                chrom=chrom_norm,
                pos=int(pos_s) - 1,  # VCF is 1-based; AlleleForge is 0-based
                ref=ref if ref != "." else "",
                alt=alt,
                source_assembly=source_assembly,
                clinvar=accession,
                rsid=rsid,
            ).normalized()
            yield ClinVarRecord(
                variant=variant,
                accession=accession,
                significance=_normalize_significance(info.get("CLNSIG")),
                review_status=info.get("CLNREVSTAT", "").replace("_", " ") or None,
                gene=gene,
                raw_significance=info.get("CLNSIG"),
            )

    def __len__(self) -> int:
        """Return the number of parsed records."""
        return len(self._records)

    def get(self, accession: str | ClinVarAccession) -> ClinVarRecord:
        """Return the record for a ``VCV`` accession.

        ClinVar's VCF carries only the integer VariationID, so records are indexed
        by their reconstructed ``VCV`` accession (see
        :func:`accession_from_variation_id`). An ``RCV``/``SCV`` accession — though
        accepted by :class:`~alleleforge.types.variant.ClinVarAccession` — cannot be
        mapped from the VCF alone, so it raises with an actionable message rather
        than a bare lookup miss.

        Raises:
            KeyError: If ``accession`` is not a ``VCV`` accession, or no ``VCV``
                record carries it.
        """
        key = ClinVarAccession(value=str(accession)).value
        if not key.startswith("VCV"):
            raise KeyError(
                f"ClinVar records are indexed by VCV accession (reconstructed from the "
                f"VCF's VariationID); {key} is an {key[:3]} accession, which cannot be "
                f"resolved from the VCF alone — supply this variant's VCV accession"
            )
        if key not in self._by_accession:
            raise KeyError(f"no ClinVar record for accession {key}")
        return self._by_accession[key]

    def by_rsid(self, rsid: str | DbSnpId) -> list[ClinVarRecord]:
        """Return all records linked to a dbSNP ``rsID`` (possibly empty)."""
        key = DbSnpId(value=str(rsid)).value
        return list(self._by_rsid.get(key, ()))

    def by_gene(self, symbol: str) -> list[ClinVarRecord]:
        """Return all records annotated to a gene symbol (case-insensitive)."""
        return list(self._by_gene.get(symbol.upper(), ()))

    def in_region(self, interval: GenomicInterval) -> list[ClinVarRecord]:
        """Return records whose variant start falls within ``interval``.

        Contigs are compared naming-independently (via :func:`canonical_contig`,
        as :meth:`GenomicInterval.overlaps` does), so a ``chr``-named record and an
        Ensembl-named interval (or vice versa) still match rather than silently
        returning nothing on the mixed-naming path.
        """
        want = canonical_contig(interval.chrom)
        return [
            rec
            for rec in self._records
            if canonical_contig(rec.variant.chrom) == want
            and interval.start <= rec.variant.pos < interval.end
        ]


#: Assembly tokens recognized in a VCF header line, longest/most-specific first.
_ASSEMBLY_TOKENS: tuple[str, ...] = ("GRCh38", "GRCh37", "NCBI36", "hg38", "hg19", "hg18")


def _sniff_assembly(header_line: str) -> str | None:
    """Return the assembly named in a VCF header line, or ``None`` if none is."""
    lowered = header_line.lower()
    for token in _ASSEMBLY_TOKENS:
        if token.lower() in lowered:
            return token
    return None


def _with_chr(chrom: str) -> str:
    """Prepend ``chr`` to a bare contig name; leave already-prefixed names."""
    if chrom.lower().startswith("chr"):
        return chrom
    if chrom in {"MT", "M"}:
        return "chrM"
    return f"chr{chrom}"
