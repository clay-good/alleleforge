"""Tests for ClinVar parsing, accession reconstruction, and lookups."""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from alleleforge.data.clinvar import (
    ClinicalSignificance,
    ClinVarDB,
    accession_from_variation_id,
)
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.types.variant import VariantClass


def test_accession_from_variation_id() -> None:
    assert accession_from_variation_id(12).value == "VCV000000012"
    assert accession_from_variation_id("334").value == "VCV000000334"


def test_parse_skips_ref_only_rows(clinvar_vcf: Path) -> None:
    db = ClinVarDB.from_vcf(clinvar_vcf)
    assert len(db) == 4  # the ALT='.' row is dropped


def test_get_by_accession_and_coordinate_conversion(clinvar_vcf: Path) -> None:
    db = ClinVarDB.from_vcf(clinvar_vcf)
    rec = db.get("VCV000000012")
    assert rec.gene == "HBB"
    assert rec.significance is ClinicalSignificance.PATHOGENIC
    assert rec.variant.chrom == "chr2"  # bare '2' gets the chr prefix
    assert rec.variant.pos == 60099  # 1-based 60100 -> 0-based
    assert rec.variant.variant_class is VariantClass.SNV
    assert str(rec.variant.rsid) == "rs334"


def test_get_unknown_accession_raises(clinvar_vcf: Path) -> None:
    db = ClinVarDB.from_vcf(clinvar_vcf)
    with pytest.raises(KeyError, match="no ClinVar record"):
        db.get("VCV000099999")


def test_get_rcv_scv_raises_actionable_not_bare_miss(clinvar_vcf: Path) -> None:
    # The VCF carries only the VariationID, so records index by VCV. An RCV/SCV
    # accession (accepted by ClinVarAccession) cannot be mapped from the VCF alone;
    # get must say so, not present a bare "no record" miss as if it were absent.
    db = ClinVarDB.from_vcf(clinvar_vcf)
    for other in ("RCV000000012", "SCV000000012"):
        with pytest.raises(KeyError, match="cannot be resolved from the VCF alone"):
            db.get(other)


def test_by_rsid(clinvar_vcf: Path) -> None:
    db = ClinVarDB.from_vcf(clinvar_vcf)
    recs = db.by_rsid("rs114518452")
    assert len(recs) == 1
    assert recs[0].gene == "BCL11A"
    assert recs[0].significance is ClinicalSignificance.LIKELY_PATHOGENIC
    assert db.by_rsid("rs999") == []


def test_by_gene_is_case_insensitive(clinvar_vcf: Path) -> None:
    db = ClinVarDB.from_vcf(clinvar_vcf)
    assert len(db.by_gene("BCL11A")) == 3
    assert len(db.by_gene("bcl11a")) == 3


def test_conflicting_significance_normalizes(clinvar_vcf: Path) -> None:
    db = ClinVarDB.from_vcf(clinvar_vcf)
    rec = db.get("VCV000000028")
    assert rec.significance is ClinicalSignificance.CONFLICTING


def test_in_region(clinvar_vcf: Path) -> None:
    db = ClinVarDB.from_vcf(clinvar_vcf)
    region = GenomicInterval(chrom="chr2", start=60099, end=60300, strand=Strand.PLUS)
    hits = db.in_region(region)
    positions = sorted(r.variant.pos for r in hits)
    assert positions == [60099, 60200]  # 60399/60449 fall outside


def test_in_region_matches_across_contig_naming(clinvar_vcf: Path) -> None:
    # Records are chr-prefixed by default; an Ensembl-named ('2') query interval must
    # still match them rather than silently returning nothing on the mixed-naming
    # path — the same naming reconciliation GenomicInterval.overlaps already does.
    db = ClinVarDB.from_vcf(clinvar_vcf)
    ensembl = GenomicInterval(chrom="2", start=60099, end=60300, strand=Strand.PLUS)
    positions = sorted(r.variant.pos for r in db.in_region(ensembl))
    assert positions == [60099, 60200]


def test_no_chr_prefix_option(clinvar_vcf: Path) -> None:
    db = ClinVarDB.from_vcf(clinvar_vcf, add_chr_prefix=False)
    assert db.get("VCV000000012").variant.chrom == "2"


def test_from_vcf_sniffs_native_assembly_from_header(tmp_path: Path) -> None:
    vcf = tmp_path / "clinvar_grch37.vcf"
    vcf.write_text(
        "##fileformat=VCFv4.2\n"
        "##reference=GRCh37\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        "2\t60100\t12\tA\tT\t.\t.\tCLNSIG=Pathogenic\n"
    )
    db = ClinVarDB.from_vcf(vcf)
    assert db.get("VCV000000012").variant.source_assembly == "GRCh37"


def test_from_vcf_assembly_unknown_when_header_silent(clinvar_vcf: Path) -> None:
    # The fixture header states no assembly, so it is recorded as unknown (None),
    # not assumed to be the default build.
    db = ClinVarDB.from_vcf(clinvar_vcf)
    assert db.get("VCV000000012").variant.source_assembly is None


def test_from_vcf_explicit_assembly_overrides_sniff(tmp_path: Path) -> None:
    vcf = tmp_path / "clinvar.vcf"
    vcf.write_text(
        "##reference=GRCh38\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        "2\t60100\t12\tA\tT\t.\t.\tCLNSIG=Pathogenic\n"
    )
    db = ClinVarDB.from_vcf(vcf, assembly="GRCh37")
    assert db.get("VCV000000012").variant.source_assembly == "GRCh37"


def test_parser_edge_cases(tmp_path: Path) -> None:
    vcf = tmp_path / "edge.vcf"
    vcf.write_text(
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        "MT\t100\t50\tA\tG\t.\t.\tCLNVC=single_nucleotide_variant\n"  # MT->chrM, no CLNSIG/gene/RS
        "2\t200\t51\tC\tT\t.\t.\t.\n"  # bare '.' INFO
        "2\t300\tshort\n"  # too few columns -> skipped
    )
    db = ClinVarDB.from_vcf(vcf)
    assert len(db) == 2
    mt = db.get("VCV000000050")
    assert mt.variant.chrom == "chrM"
    assert mt.significance is ClinicalSignificance.NOT_PROVIDED
    assert mt.gene is None and mt.variant.rsid is None


def test_reads_gzipped_vcf(clinvar_vcf: Path, tmp_path: Path) -> None:
    gz = tmp_path / "clinvar.vcf.gz"
    gz.write_bytes(gzip.compress(clinvar_vcf.read_bytes()))
    db = ClinVarDB.from_vcf(gz)
    assert len(db) == 4
