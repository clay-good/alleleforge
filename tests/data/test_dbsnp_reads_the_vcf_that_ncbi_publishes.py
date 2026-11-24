"""dbSNP's published release is a VCF, and this class could only read a TSV.

The gap was visible from two directions and neither had been followed. `DbSnpDB` had one
reader, `from_tsv`, wanting an `rsid chrom pos ref alt` table. `variant/resolver.py`'s own
refusal told callers to use "`DbSnpDB.from_tsv(path)` … an `rsid chrom pos ref alt`" file.
And the dataset registry describes `dbsnp` with `source_url` pointing at
`GCF_000001405.40.gz` — NCBI's VCF. So the product named an artifact it could not open and
instructed the reader to convert it by hand, with no tool to do so.

R700 found the sharp end of this: pinning that descriptor's `sha256` would switch the
fetch path on, download 26.6 GB and save it under a `.tsv.gz` name the loader then
rejects. The fix is not to pin it; the fix is to read what upstream publishes.

Three details of dbSNP's VCF that a generic reader gets wrong, each pinned below against
rows taken from the real b156 release rather than invented:

* **contigs are versioned RefSeq accessions** (`NC_000001.11`), so a reader that strips a
  `chr` prefix emits contigs no reference has;
* **ALT is multi-allelic** — in a 400-row slice, 537 alleles come from 363 rsIDs, so one
  variant per row drops a quarter of them;
* **the published filename contains no `.vcf`**, so dispatch must sniff content.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from alleleforge.data.dbsnp import DbSnpDB
from alleleforge.types.sequence import contig_from_refseq

#: Rows copied from dbSNP b156 (`GCF_000001405.40.gz`), including the multi-allelic first
#: record. Verbatim so the parser is held to upstream's real shape, not to a tidy fixture.
_REAL_ROWS = """\
##fileformat=VCFv4.2
##INFO=<ID=RS,Number=1,Type=Integer,Description="dbSNP ID">
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
NC_000001.11\t10001\trs1570391677\tT\tA,C\t.\t.\tRS=1570391677;VC=SNV
NC_000001.11\t10002\trs1570391692\tA\tC\t.\t.\tRS=1570391692;VC=SNV
NC_000023.11\t2781479\trs2000001\tG\tT\t.\t.\tRS=2000001;VC=SNV
NT_187361.1\t500\trs999999999\tA\tG\t.\t.\tRS=999999999;VC=SNV
NC_000001.11\t10500\t.\tA\tG\t.\t.\tVC=SNV
NC_000001.11\t10600\trs3000001\tA\t<DEL>\t.\t.\tVC=SV
"""


@pytest.fixture
def vcf(tmp_path: Path) -> Path:
    path = tmp_path / "dbsnp.vcf"
    path.write_text(_REAL_ROWS)
    return path


# -- the accession mapping -----------------------------------------------------


@pytest.mark.parametrize(
    "accession, contig",
    [
        ("NC_000001.11", "chr1"),
        ("NC_000023.11", "chrX"),
        ("NC_000024.10", "chrY"),
        ("NC_012920.1", "chrM"),
        # Version suffixes differ between assemblies; the caller has already decided
        # which release it is reading, so the suffix is dropped rather than matched.
        ("NC_000001.10", "chr1"),
    ],
)
def test_a_refseq_accession_maps_to_its_contig(accession: str, contig: str) -> None:
    assert contig_from_refseq(accession) == contig


@pytest.mark.parametrize("other", ["NT_187361.1", "NW_009646201.1", "chr1", "1", ""])
def test_an_unplaced_or_already_named_contig_is_not_mapped(other: str) -> None:
    """`None`, not an exception: a release carries thousands of scaffolds.

    Refusing them would make the whole file unreadable over contigs no caller asked
    about, and `chr1` returning `None` is what keeps this helper from quietly
    double-translating an already-UCSC name.
    """
    assert contig_from_refseq(other) is None


def test_the_map_is_shared_with_the_hgvs_resolver() -> None:
    """One table, because genomic HGVS and dbSNP's VCF both speak accessions.

    It lived privately in `variant/resolver.py` and was promoted rather than copied. Two
    copies of a lookup table are two things that drift, and this project has already been
    bitten by a guard written twice and pinned neither time.
    """
    from alleleforge.variant.resolver import resolve

    assert contig_from_refseq("NC_000002.12") == "chr2"
    # And the resolver still answers through it.
    assert resolve("NC_000002.12:g.60100A>T", reference=None).variant.chrom == "chr2"


# -- reading the VCF -----------------------------------------------------------


def test_a_published_vcf_loads(vcf: Path) -> None:
    db = DbSnpDB.from_vcf(vcf, assembly="GRCh38")
    variant = db.locus("rs1570391692")
    assert variant.chrom == "chr1"
    assert variant.pos == 10001, "VCF POS is 1-based; this model stores 0-based"
    assert (variant.ref, variant.alt) == ("A", "C")
    assert variant.source_assembly == "GRCh38"


def test_every_allele_of_a_multi_allelic_row_is_kept(vcf: Path) -> None:
    """One row, two alleles, two variants.

    `rs1570391677` is `T -> A,C` in the real release. Keeping one allele per row would
    drop a quarter of the records in a 400-row slice, from a database whose only job is
    to say which alleles exist at a site.
    """
    alleles = {v.alt for v in DbSnpDB._parse_vcf(vcf, assembly="GRCh38") if v.pos == 10000}
    assert alleles == {"A", "C"}, alleles


def test_locus_answers_with_one_allele_of_a_multi_allelic_site(vcf: Path) -> None:
    """A pre-existing limitation, pinned so it is known rather than discovered.

    `_by_rsid` is a plain dict keyed by rsID, so a multi-allelic site keeps the last
    allele read while `rsids_at` sees all of them. The TSV path could always reach this
    by listing an rsID twice; nothing produced such input until this reader existed.
    Widening `locus` to return every allele changes a public return type, so it is
    recorded here rather than changed in passing.
    """
    db = DbSnpDB.from_vcf(vcf, assembly="GRCh38")
    assert db.locus("rs1570391677").alt == "C"  # the last of `A,C`


@pytest.mark.parametrize(
    "rsid, why",
    [
        ("rs999999999", "sits on an unplaced scaffold (NT_) no reference carries"),
        ("rs3000001", "its only ALT is the symbolic <DEL>"),
    ],
)
def test_a_row_that_cannot_become_a_variant_is_skipped(vcf: Path, rsid: str, why: str) -> None:
    """Skipped, not raised: a whole-genome release carries many of each.

    Refusing either would make the file unreadable over records a caller never asked
    about — the same reason the sibling loaders skip symbolic alleles.
    """
    db = DbSnpDB.from_vcf(vcf, assembly="GRCh38")
    with pytest.raises(KeyError):
        db.locus(rsid)


def test_a_row_with_no_rs_number_is_skipped(vcf: Path) -> None:
    """`ID` of `.` means no dbSNP identity, and identity is this class's only key."""
    positions = {v.pos for v in DbSnpDB._parse_vcf(vcf, assembly="GRCh38")}
    assert 10499 not in positions, "the ID='.' row was indexed"


# -- dispatch by content, not by name ------------------------------------------


def test_the_published_filename_has_no_vcf_in_it(tmp_path: Path) -> None:
    """`load` must accept `GCF_000001405.40.gz`, which is what NCBI actually serves.

    This is the whole reason dispatch sniffs the first line. A reader switching on
    `.vcf` rejects the only artifact upstream publishes — and that is how the project
    came to instruct callers to convert it by hand.
    """
    published = tmp_path / "GCF_000001405.40.gz"
    with gzip.open(published, "wt") as handle:
        handle.write(_REAL_ROWS)

    db = DbSnpDB.load(published, assembly="GRCh38")
    assert db.locus("rs1570391692").chrom == "chr1"


def test_the_project_tsv_still_loads_through_the_same_door(tmp_path: Path) -> None:
    """The other half of the sniff, so adding VCF support did not cost TSV support."""
    tsv = tmp_path / "dbsnp.tsv"
    tsv.write_text("#rsid\tchrom\tpos\tref\talt\nrs1\t2\t100\tA\tT\n")
    assert DbSnpDB.load(tsv).locus("rs1").chrom == "chr2"


def test_a_non_vcf_is_diagnosed_by_the_tsv_reader_not_by_the_sniff(tmp_path: Path) -> None:
    """Dispatch is on the positive VCF signal; everything else goes to `from_tsv`.

    An earlier draft of `load` raised its own "neither a VCF nor a TSV" error. That
    intercepted a TSV with the *wrong columns* and replaced `from_tsv`'s diagnosis —
    which names the expected header and the one it found, column by column — with a
    restatement of the two formats. Two existing tests caught it
    (`test_a_refusal_names_a_remedy_that_works`,
    `test_the_dbsnp_schema_is_named_both_ways`), and they were right: a reader whose file
    is nearly right needs the comparison, not a description.

    So `load` adds no error of its own, and this pins that the detailed one still
    arrives through it.
    """
    nearly = tmp_path / "sites.tsv"
    nearly.write_text("#chrom\tpos\tref\talt\taf\nchr1\t100\tA\tT\t0.1\n")

    with pytest.raises(ValueError, match="header is missing") as refused:
        DbSnpDB.load(nearly)
    message = str(refused.value)
    assert "rsid" in message, message
    assert "found:" in message, ("the column-by-column comparison was lost", message)
