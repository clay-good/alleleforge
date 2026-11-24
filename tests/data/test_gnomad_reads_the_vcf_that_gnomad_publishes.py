"""gnomAD publishes VCFs, and the only reader wanted a table nothing produced.

Population-aware off-target search is what this project is built around, and
`GnomadDB`'s only reader was `from_sites_tsv`, wanting `chrom pos ref alt af <pop>...`.
The registry's `gnomad` descriptor points at the download portal. No converter ships. So
the input behind the headline capability required the caller to write a VCF-to-TSV
conversion first — the same defect R701 fixed for dbSNP, in the dataset that matters most.

Found by applying R701's own query to every loader: *does the artifact the registry points
at match what the reader accepts?* `clinvar` has `from_vcf`, `gencode` has `from_gtf`,
`dbsnp` got `from_vcf` — gnomAD, `1000g`, `hgdp` and `encode` did not.

Every fixture below is a **real row** from
`gnomad.genomes.v4.1.sites.chr22.vcf.bgz`, not an invented one, because the defect this
file is mostly about is only visible in upstream's real INFO field.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from alleleforge.data.gnomad import GNOMAD_POPULATIONS, GnomadDB

#: A real PASS row from chr22, with its INFO reduced to the ten ancestry keys plus every
#: `AF_*` key that is *not* an ancestry. Those traps are the point: `AF_XX`, `AF_XY`,
#: `AF_afr_XX`, `AF_nfe_XY`, `AF_grpmax` and `AF_raw` all match a naive `AF_*` pattern.
_REAL_PASS_ROW = (
    "chr22\t10526438\t.\tA\tG\t.\tPASS\t"
    "AF=0.934124;AF_XX=0.933952;AF_XY=0.934308;AF_afr_XX=0.855565;AF_afr=0.856539;"
    "AF_ami=0.970982;AF_amr=0.914391;AF_asj=0.965012;AF_eas=0.943654;AF_fin=0.996260;"
    "AF_mid=0.929487;AF_nfe_XY=0.984833;AF_nfe=0.985232;AF_raw=0.943988;"
    "AF_remaining=0.940459;AF_sas=0.990068;AF_grpmax=0.990068"
)

#: A real non-PASS row: gnomAD's own verdict that the call is unreliable.
_REAL_FILTERED_ROW = (
    "chr22\t10510033\t.\tT\tC\t.\tAC0;AS_VQSR\t"
    "AC=0;AN=6;AF=0.00000;AF_XX=0.00000;AF_afr=0.00000;AF_amr=0.00000"
)

_HEADER = "##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"


@pytest.fixture
def vcf(tmp_path: Path) -> Path:
    path = tmp_path / "sites.vcf"
    path.write_text(_HEADER + _REAL_PASS_ROW + "\n" + _REAL_FILTERED_ROW + "\n")
    return path


# -- the defect that matters: most AF_* keys are not ancestries ----------------


def test_only_real_ancestry_groups_become_populations(vcf: Path) -> None:
    """The sharp one. A naive `AF_*` match advertises sex strata as ancestries.

    This project reports which ancestries a scan *examined*, and
    `available_populations` is what it reports from. Admitting `AF_XX` would put `XX` in
    that set — a caller could then "stratify by XX" and the provenance would claim an
    ancestry was considered that does not exist. A false coverage claim, not a cosmetic
    slip.
    """
    db = GnomadDB.from_vcf(vcf)
    assert db.available_populations == frozenset(GNOMAD_POPULATIONS)


@pytest.mark.parametrize("trap", ["XX", "XY", "afr_XX", "nfe_XY", "grpmax", "raw"])
def test_a_non_ancestry_af_key_is_not_a_population(vcf: Path, trap: str) -> None:
    """Each trap named individually, because they are wrong in different ways.

    `XX`/`XY` are sex strata; `afr_XX`/`nfe_XY` are ancestry crossed with sex;
    `grpmax` is a maximum *across* groups; `raw` is the pre-filter frequency. All six are
    in the real row above, and all six match `AF_*`.
    """
    assert trap not in GnomadDB.from_vcf(vcf).available_populations


def test_the_real_row_carries_the_traps_so_this_is_not_a_tidy_fixture() -> None:
    """Guard the fixture itself: if the traps were dropped, the tests above pass empty.

    A later tidy-up that simplified `_REAL_PASS_ROW` to only the ancestry keys would
    leave every assertion above true and measuring nothing.
    """
    for trap in ("AF_XX=", "AF_XY=", "AF_afr_XX=", "AF_nfe_XY=", "AF_grpmax=", "AF_raw="):
        assert trap in _REAL_PASS_ROW, trap


# -- the frequencies themselves ------------------------------------------------


def test_the_overall_and_per_ancestry_frequencies_are_read(vcf: Path) -> None:
    """Values checked against the real row, including the 0-based coordinate shift."""
    db = GnomadDB.from_vcf(vcf)
    record = next(r for v in db._by_chrom.values() for r in v)

    assert record.chrom == "chr22"
    assert record.pos == 10526437, "VCF POS is 1-based; this model stores 0-based"
    assert (record.ref, record.alt) == ("A", "G")
    assert record.overall_af == pytest.approx(0.934124)
    assert record.populations["afr"] == pytest.approx(0.856539)
    assert record.populations["sas"] == pytest.approx(0.990068)
    assert len(record.populations) == len(GNOMAD_POPULATIONS)


def test_a_non_pass_row_is_skipped(vcf: Path) -> None:
    """`AC0;AS_VQSR` is gnomAD saying the call is unreliable.

    Skipped because a frequency this tool puts in front of somebody should be one
    upstream stands behind. It is also most of a real file's head: of 11,291 rows in the
    slice this fixture came from, 1,976 pass — so including them would multiply the
    record count by five with calls gnomAD itself rejects.
    """
    db = GnomadDB.from_vcf(vcf)
    positions = {r.pos for v in db._by_chrom.values() for r in v}
    assert 10510032 not in positions, "the AC0;AS_VQSR row was indexed"
    assert positions == {10526437}


def test_an_absent_group_is_omitted_rather_than_recorded_as_zero(tmp_path: Path) -> None:
    """A group's key is missing when it has no data at that site, which is not 0.0.

    Recording absence as zero would say "measured, and nobody carries it" where the
    truth is "not measured here" — and `available_populations` would then advertise an
    ancestry the file never reported on.
    """
    path = tmp_path / "sparse.vcf"
    path.write_text(_HEADER + "chr22\t100\t.\tA\tG\t.\tPASS\tAF=0.5;AF_afr=0.25\n")

    db = GnomadDB.from_vcf(path)
    record = next(r for v in db._by_chrom.values() for r in v)
    assert record.populations == {"afr": pytest.approx(0.25)}
    assert db.available_populations == frozenset({"afr"})


def test_a_multi_allelic_row_lines_frequencies_up_with_alleles(tmp_path: Path) -> None:
    """`AF` is `Number=A`, so a comma-separated row is one value per ALT.

    gnomAD v4 ships allele-split sites — no multi-allelic rows in the slice checked —
    but VCF permits them and another release or a caller's own extract may carry them.
    Taking `AF` as a scalar there would attach the first allele's frequency to every
    allele.
    """
    path = tmp_path / "multi.vcf"
    path.write_text(_HEADER + "chr22\t200\t.\tA\tG,T\t.\tPASS\tAF=0.4,0.1;AF_nfe=0.5,0.2\n")

    by_alt = {r.alt: r for v in GnomadDB.from_vcf(path)._by_chrom.values() for r in v}
    assert by_alt["G"].overall_af == pytest.approx(0.4)
    assert by_alt["T"].overall_af == pytest.approx(0.1)
    assert by_alt["G"].populations["nfe"] == pytest.approx(0.5)
    assert by_alt["T"].populations["nfe"] == pytest.approx(0.2)


def test_a_symbolic_allele_is_skipped(tmp_path: Path) -> None:
    """`*` and `<DEL>` are not literal sequence; the sibling loaders skip them too."""
    path = tmp_path / "sym.vcf"
    path.write_text(_HEADER + "chr22\t300\t.\tA\t*\t.\tPASS\tAF=0.5\n")
    assert not GnomadDB.from_vcf(path)._by_chrom


# -- dispatch ------------------------------------------------------------------


def test_the_published_bgz_filename_opens_at_all(tmp_path: Path) -> None:
    """gnomAD publishes `.bgz`, and `open_text` keyed compression off `.gz`.

    So the reader could not open the file the dataset is actually released as — and the
    failure was not a clear refusal: the gzip bytes reached the UTF-8 decoder and came
    out as `UnicodeDecodeError: invalid start byte`, which reads as a corrupt file rather
    than an unrecognised extension. This test found it, with the published filename.

    `open_text` now detects gzip by its magic bytes, which also covers an extract a
    caller saved with no suffix, and fixes it for every loader at once rather than for
    gnomAD alone. bgzf is concatenated gzip members, which `gzip` reads as one stream.
    """
    published = tmp_path / "gnomad.genomes.v4.1.sites.chr22.vcf.bgz"
    with gzip.open(published, "wt") as handle:
        handle.write(_HEADER + _REAL_PASS_ROW + "\n")

    assert GnomadDB.load(published).available_populations == frozenset(GNOMAD_POPULATIONS)


def test_a_gzip_file_with_no_suffix_at_all_opens(tmp_path: Path) -> None:
    """The general case the magic-byte check buys, beyond `.bgz`.

    An extension is a naming convention; the bytes are the fact. A caller who saved an
    extract as `sites` gets the same reader as one who kept upstream's name.
    """
    nameless = tmp_path / "sites"
    with gzip.open(nameless, "wt") as handle:
        handle.write(_HEADER + _REAL_PASS_ROW + "\n")

    assert GnomadDB.load(nameless).available_populations == frozenset(GNOMAD_POPULATIONS)


def test_the_sites_tsv_still_loads_through_the_same_door(tmp_path: Path) -> None:
    """Adding VCF support must not cost the TSV path."""
    tsv = tmp_path / "sites.tsv"
    tsv.write_text("#chrom\tpos\tref\talt\taf\tnfe\nchr1\t100\tA\tT\t0.2\t0.3\n")
    db = GnomadDB.load(tsv)
    assert db.available_populations == frozenset({"nfe"})


def test_a_nearly_right_tsv_keeps_its_column_by_column_diagnosis(tmp_path: Path) -> None:
    """`load` adds no error of its own, for the reason R701 recorded.

    Its first draft there raised "neither a VCF nor a TSV" and replaced the header
    check's expected-versus-found comparison with a vaguer restatement. Dispatch is on
    the positive VCF signal only, so a file that is nearly a sites TSV still gets the
    message that tells the caller which column is missing.
    """
    nearly = tmp_path / "nearly.tsv"
    nearly.write_text("#chrom\tpos\tref\talt\nchr1\t100\tA\tT\n")

    with pytest.raises(ValueError, match="header is missing") as refused:
        GnomadDB.load(nearly)
    assert "af" in str(refused.value)


def test_the_declared_ancestry_list_matches_what_a_real_row_carries() -> None:
    """The list was seven long and the file carries ten.

    `GNOMAD_POPULATIONS` omitted `ami` (Amish), `mid` (Middle Eastern) and `remaining`,
    so a reader filtering on it dropped two *named ancestries* from the dataset whose
    whole purpose is population awareness. Pinned against the ancestry keys of a real
    v4.1 row so the list cannot quietly fall behind a release again.
    """
    carried = {
        entry.split("=")[0][len("AF_") :]
        for entry in _REAL_PASS_ROW.split("\t")[-1].split(";")
        if entry.startswith("AF_")
    }
    ancestries = {
        group
        for group in carried
        if not group.endswith(("_XX", "_XY")) and group not in {"XX", "XY", "grpmax", "raw"}
    }
    assert ancestries == set(GNOMAD_POPULATIONS), (sorted(ancestries ^ set(GNOMAD_POPULATIONS)),)


def test_the_registry_descriptor_and_the_reader_share_one_list() -> None:
    """Two copies of this list existed and both were wrong the same way.

    The descriptor hard-coded its own seven-element tuple beside the module's. They
    agreed, which is why nobody noticed either was incomplete — agreement between two
    copies is not evidence that either is right.
    """
    from alleleforge.data.registry import DEFAULT_REGISTRY

    assert DEFAULT_REGISTRY.get("gnomad").populations == GNOMAD_POPULATIONS
