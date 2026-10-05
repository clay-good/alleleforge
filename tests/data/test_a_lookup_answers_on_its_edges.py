"""The data layer's lookups and parsers, tested on their edges.

A mutation sweep of `data/`, confirmed against the full suite, left six real survivors.
Each was a fixture that sat inside a threshold instead of on it:

* region queries are half-open, `[start, end)`, and no fixture had a record at `end`, so
  `pos <= end` passed in both ClinVar and dbSNP, and `start < pos` passed in dbSNP;
* a ClinVar insertion written with REF `.` (no anchor base) is kept with an empty REF,
  and no fixture had one, so a check that silently skipped every such row passed;
* a truncated GENCODE line is skipped, and no fixture had one, so a guard that let it
  through to an `IndexError` passed;
* a descriptor that is not bundled must not resolve a bundled path, whatever its
  `bundled_path` says.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.data.annotations import GeneModels
from alleleforge.data.clinvar import ClinVarDB
from alleleforge.data.dbsnp import DbSnpDB
from alleleforge.data.registry import DatasetDescriptor
from alleleforge.types.sequence import GenomicInterval, Strand

_VCF_HEADER = "##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"


def _region(start: int, end: int) -> GenomicInterval:
    return GenomicInterval(chrom="chr2", start=start, end=end, strand=Strand.PLUS)


#: A record at 1-based 101 is 0-based 100: inside [100, 101), outside [99, 100) and
#: [101, 102). The two outside windows each touch it on one side.
_EDGES = [((100, 101), True), ((99, 100), False), ((101, 102), False)]


@pytest.mark.parametrize(("window", "inside"), _EDGES)
def test_a_clinvar_region_is_half_open(
    tmp_path: Path, window: tuple[int, int], inside: bool
) -> None:
    vcf = tmp_path / "clinvar.vcf"
    vcf.write_text(_VCF_HEADER + "2\t101\t12\tA\tG\t.\t.\tCLNSIG=Pathogenic\n")
    db = ClinVarDB.from_vcf(vcf)
    assert bool(db.in_region(_region(*window))) is inside


@pytest.mark.parametrize(("window", "inside"), _EDGES)
def test_a_dbsnp_region_is_half_open(tmp_path: Path, window: tuple[int, int], inside: bool) -> None:
    tsv = tmp_path / "dbsnp.tsv"
    tsv.write_text("#rsid\tchrom\tpos\tref\talt\nrs334\t2\t101\tA\tG\n")
    db = DbSnpDB.from_tsv(tsv)
    assert bool(db.rsids_at(_region(*window))) is inside


def test_a_clinvar_insertion_without_an_anchor_base_is_kept(tmp_path: Path) -> None:
    vcf = tmp_path / "clinvar.vcf"
    vcf.write_text(
        _VCF_HEADER
        + "2\t101\t12\t.\tAT\t.\t.\tCLNSIG=Pathogenic\n"
        + "2\t301\t14\tG\tT\t.\t.\tCLNSIG=Pathogenic\n"
    )
    db = ClinVarDB.from_vcf(vcf)
    assert len(db) == 2
    (insertion,) = db.in_region(_region(90, 110))
    assert insertion.variant.ref == "" and insertion.variant.alt.endswith("AT")


def test_a_truncated_gencode_line_is_skipped_not_fatal(gencode_gtf: Path, tmp_path: Path) -> None:
    gtf = tmp_path / "truncated.gtf"
    gtf.write_text("chr2\tHAVANA\tgene\n" + gencode_gtf.read_text())
    assert GeneModels.from_gtf(gtf).gene("BCL11A").interval.start == 60000


@pytest.mark.parametrize(
    ("bundled", "bundled_path"), [(False, "data/fixtures/x.tsv"), (True, None)]
)
def test_only_a_bundled_descriptor_with_a_path_resolves_one(
    bundled: bool, bundled_path: str | None
) -> None:
    descriptor = DatasetDescriptor(
        name="demo",
        version="1.0",
        source_url="https://example.org/demo.tsv",
        license="CC0-1.0",
        citation="Demo et al. 2024",
        redistributable=True,
        filename="demo.tsv",
        bundled=bundled,
        bundled_path=bundled_path,
    )
    assert descriptor.bundled_file() is None
