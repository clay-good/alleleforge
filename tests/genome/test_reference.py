"""Tests for reference-genome access: strand-aware, padded, consent-gated."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from alleleforge.genome.reference import (
    BUILTIN_BUILDS,
    BuildDescriptor,
    ChecksumError,
    ConsentError,
    ReferenceGenome,
)
from alleleforge.types.sequence import CoordinateSystem, GenomicInterval, Strand

_FASTA_TEXT = ">chr1\nACGTACGTACGTACGTACGT\n>chr2\nTTTTGGGGCCCCAAAANNNN\n"


def _iv(chrom: str, start: int, end: int, strand: Strand = Strand.PLUS) -> GenomicInterval:
    return GenomicInterval(chrom=chrom, start=start, end=end, strand=strand)


def test_contigs_and_lengths(tiny_fasta: Path) -> None:
    with ReferenceGenome(tiny_fasta) as ref:
        assert set(ref.contigs) == {"chr1", "chr2"}
        assert ref.contig_length("chr1") == 20
        assert ref.contig_length("chr2") == 20


def test_contig_length_unknown_raises(tiny_fasta: Path) -> None:
    with ReferenceGenome(tiny_fasta) as ref, pytest.raises(KeyError, match="unknown contig"):
        ref.contig_length("chrX")


def test_fetch_plus_strand_known_locus(tiny_fasta: Path) -> None:
    with ReferenceGenome(tiny_fasta) as ref:
        assert str(ref.fetch(_iv("chr1", 0, 4))) == "ACGT"
        assert str(ref.fetch(_iv("chr1", 4, 8))) == "ACGT"
        assert str(ref.fetch(_iv("chr1", 0, 20))) == "ACGTACGTACGTACGTACGT"


def test_fetch_minus_strand_reverse_complements(tiny_fasta: Path) -> None:
    with ReferenceGenome(tiny_fasta) as ref:
        # plus chr1[0:6] = ACGTAC; revcomp = GTACGT
        assert str(ref.fetch(_iv("chr1", 0, 6, Strand.MINUS))) == "GTACGT"


def test_fetch_pads_contig_end_with_n_and_flags(tiny_fasta: Path) -> None:
    with ReferenceGenome(tiny_fasta) as ref:
        result = ref.fetch_result(_iv("chr1", 18, 24))
        assert str(result.sequence) == "GTNNNN"
        assert result.padded
        assert result.right_pad == 4
        assert result.left_pad == 0


def test_fetch_entirely_past_end_is_all_n(tiny_fasta: Path) -> None:
    with ReferenceGenome(tiny_fasta) as ref:
        result = ref.fetch_result(_iv("chr1", 25, 30))
        assert str(result.sequence) == "NNNNN"
        assert result.right_pad == 5


def test_fetch_within_bounds_is_not_padded(tiny_fasta: Path) -> None:
    with ReferenceGenome(tiny_fasta) as ref:
        assert not ref.fetch_result(_iv("chr1", 0, 4)).padded


def test_fetch_rejects_one_based_interval(tiny_fasta: Path) -> None:
    iv = GenomicInterval(
        chrom="chr1",
        start=1,
        end=4,
        strand=Strand.PLUS,
        coordinate_system=CoordinateSystem.ONE_BASED,
    )
    with ReferenceGenome(tiny_fasta) as ref, pytest.raises(ValueError, match="0-based"):
        ref.fetch(iv)


def test_fetch_unknown_contig_raises(tiny_fasta: Path) -> None:
    with ReferenceGenome(tiny_fasta) as ref, pytest.raises(KeyError, match="unknown contig"):
        ref.fetch(_iv("chrX", 0, 4))


def test_builtin_builds_present() -> None:
    assert {"hg38", "T2T-CHM13v2", "mm39"} <= set(BUILTIN_BUILDS)
    dv = BUILTIN_BUILDS["hg38"].dataset_version()
    assert dv.name == "hg38"
    assert dv.redistributable is False


def test_from_build_unknown_build_raises() -> None:
    with pytest.raises(KeyError, match="unknown build"):
        ReferenceGenome.from_build("nope", cache_dir="/tmp/none", consent=True)


def test_from_build_without_consent_refuses(tmp_path: Path) -> None:
    desc = BuildDescriptor(
        name="synth", version="v1", source_url="http://x/y.fa", citation="c", sha256="00"
    )
    with pytest.raises(ConsentError, match="consent=True"):
        ReferenceGenome.from_build("synth", cache_dir=tmp_path, consent=False, descriptor=desc)


def test_from_build_refuses_unverifiable_download(tmp_path: Path) -> None:
    desc = BuildDescriptor(
        name="synth", version="v1", source_url="http://x/y.fa", citation="c", sha256=None
    )
    with pytest.raises(ChecksumError, match="unverifiable"):
        ReferenceGenome.from_build("synth", cache_dir=tmp_path, consent=True, descriptor=desc)


def test_from_build_downloads_verifies_and_opens(tmp_path: Path) -> None:
    digest = hashlib.sha256(_FASTA_TEXT.encode()).hexdigest()
    desc = BuildDescriptor(
        name="synth", version="v1", source_url="http://x/y.fa", citation="cite", sha256=digest
    )

    def fake_downloader(url: str, dest: Path) -> None:
        dest.write_text(_FASTA_TEXT)

    ref = ReferenceGenome.from_build(
        "synth", cache_dir=tmp_path, consent=True, descriptor=desc, downloader=fake_downloader
    )
    try:
        assert str(ref.fetch(_iv("chr1", 0, 4))) == "ACGT"
        assert ref.dataset_version is not None
        assert ref.dataset_version.sha256 == digest
    finally:
        ref.close()


def test_from_build_checksum_mismatch_raises(tmp_path: Path) -> None:
    desc = BuildDescriptor(
        name="synth", version="v1", source_url="http://x/y.fa", citation="c", sha256="deadbeef"
    )

    def fake_downloader(url: str, dest: Path) -> None:
        dest.write_text(_FASTA_TEXT)

    with pytest.raises(ChecksumError, match="checksum mismatch"):
        ReferenceGenome.from_build(
            "synth", cache_dir=tmp_path, consent=True, descriptor=desc, downloader=fake_downloader
        )


def test_from_build_uses_cached_copy_without_downloading(tmp_path: Path) -> None:
    desc = BuildDescriptor(
        name="synth", version="v1", source_url="http://x/y.fa", citation="c", sha256=None
    )
    # Pre-place the cached FASTA so no download (and no checksum) is needed.
    (tmp_path / f"{desc.name}.{desc.version}.fa").write_text(_FASTA_TEXT)
    ref = ReferenceGenome.from_build("synth", cache_dir=tmp_path, consent=False, descriptor=desc)
    try:
        assert str(ref.fetch(_iv("chr2", 0, 4))) == "TTTT"
    finally:
        ref.close()


def test_from_build_reverifies_cached_reference_on_read(tmp_path: Path) -> None:
    # A pinned build is re-hashed on every open: a tampered cached FASTA is
    # rejected on load, without any new download (consent=False).
    digest = hashlib.sha256(_FASTA_TEXT.encode()).hexdigest()
    desc = BuildDescriptor(
        name="synth", version="v1", source_url="http://x/y.fa", citation="c", sha256=digest
    )

    def fake_downloader(url: str, dest: Path) -> None:
        dest.write_text(_FASTA_TEXT)

    ReferenceGenome.from_build(
        "synth", cache_dir=tmp_path, consent=True, descriptor=desc, downloader=fake_downloader
    ).close()
    (tmp_path / f"{desc.name}.{desc.version}.fa").write_text(_FASTA_TEXT + "TAMPERED\n")
    with pytest.raises(ChecksumError, match="checksum mismatch"):
        ReferenceGenome.from_build("synth", cache_dir=tmp_path, consent=False, descriptor=desc)


def test_concurrent_fetches_are_thread_safe(tiny_fasta: Path) -> None:
    # A single ReferenceGenome is shared across threads by the web server (its
    # sync handlers run in a threadpool). pyfaidx has a shared file position, so
    # without the per-instance read lock concurrent fetches race and threads read
    # each other's bytes. Fetch many varied intervals concurrently and assert each
    # returns exactly its expected slice.
    import concurrent.futures

    full = "ACGTACGTACGTACGTACGT"
    cases = [(s, e, full[s:e]) for s in range(0, 16) for e in range(s + 1, 21)]
    ref = ReferenceGenome(tiny_fasta)

    def _check(case: tuple[int, int, str]) -> bool:
        s, e, expected = case
        return all(str(ref.fetch(_iv("chr1", s, e))) == expected for _ in range(10))

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(_check, cases))
    finally:
        ref.close()
    assert all(results)
