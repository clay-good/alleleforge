"""Tests for reference-genome access: strand-aware, padded, consent-gated."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from alleleforge.errors import ReferenceIndexError
from alleleforge.genome.reference import (
    BUILTIN_BUILDS,
    BuildDescriptor,
    ChecksumError,
    ConsentError,
    ContigNamingError,
    ReferenceGenome,
)
from alleleforge.types.sequence import CoordinateSystem, GenomicInterval, Strand

_FASTA_TEXT = ">chr1\nACGTACGTACGTACGTACGT\n>chr2\nTTTTGGGGCCCCAAAANNNN\n"


def _iv(chrom: str, start: int, end: int, strand: Strand = Strand.PLUS) -> GenomicInterval:
    return GenomicInterval(chrom=chrom, start=start, end=end, strand=strand)


def _write_fasta(tmp_path: Path, contigs: dict[str, str]) -> Path:
    fasta = tmp_path / "ref.fa"
    fasta.write_text("".join(f">{c}\n{s}\n" for c, s in contigs.items()))
    return fasta


def test_naming_style_detected(tmp_path: Path, tiny_fasta: Path) -> None:
    with ReferenceGenome(tiny_fasta) as ucsc:
        assert ucsc.naming_style == "ucsc"
    ens = _write_fasta(tmp_path, {"17": "ACGTACGTACGTACGT"})
    with ReferenceGenome(ens) as ref:
        assert ref.naming_style == "ensembl"


def test_fetch_aliases_chr_query_against_ensembl_reference(tmp_path: Path) -> None:
    fa = _write_fasta(tmp_path, {"17": "ACGTACGTACGTACGT", "MT": "GGGGCCCCTTTTAAAA"})
    with ReferenceGenome(fa) as ref:
        # A chr-prefixed query resolves against an Ensembl-named reference...
        assert str(ref.fetch(_iv("chr17", 0, 4))) == "ACGT"
        assert ref.contig_length("chr17") == 16
        # ...and both mitochondrion spellings alias to Ensembl 'MT'.
        assert str(ref.fetch(_iv("chrM", 0, 4))) == "GGGG"
        assert str(ref.fetch(_iv("M", 0, 4))) == "GGGG"


def test_fetch_aliases_bare_query_against_ucsc_reference(tiny_fasta: Path) -> None:
    with ReferenceGenome(tiny_fasta) as ref:
        assert str(ref.fetch(_iv("1", 0, 4))) == "ACGT"  # bare '1' aliases to chr1


def test_contig_naming_mismatch_is_distinct_from_unknown(tmp_path: Path) -> None:
    fa = _write_fasta(tmp_path, {"Chr9": "ACGTACGT"})  # nonstandard mixed-case prefix
    with ReferenceGenome(fa) as ref:
        # canonical match but no exact/alias hit → an explicit naming-mismatch error,
        # never a misleading unknown-contig or wrong-build message
        with pytest.raises(ContigNamingError, match="contig-naming mismatch"):
            ref.fetch(_iv("9", 0, 4))
        # a genuinely-absent contig stays a plain unknown-contig KeyError
        with pytest.raises(KeyError, match="unknown contig"):
            ref.fetch(_iv("22", 0, 4))


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


# -- references that look like real ones ----------------------------------------
#
# Two mutation survivors here shared a root: the fixtures are uniform. `naming_style` is
# checked on an all-`chr` reference and an all-bare one, and the naming-mismatch error on a
# reference holding a *single* contig — where `any(...)` and `all(...)` are the same thing.
# A real assembly is neither: hg38 carries chr1..chrY beside `GL000009.2`-style scaffolds.


def test_naming_style_is_ucsc_when_only_some_contigs_are_chr_prefixed(tmp_path: Path) -> None:
    """`any(c.startswith("chr"))` — a real assembly's scaffolds are not chr-prefixed.

    Tightened to `all`, hg38 with its unplaced scaffolds reports as Ensembl-named, and
    every alias lookup for a `chr`-prefixed query is then resolved the wrong way round.
    """
    mixed = _write_fasta(tmp_path, {"chr1": "ACGTACGTAC", "GL000009.2": "TTTTGGGG"})
    with ReferenceGenome(mixed) as ref:
        assert ref.naming_style == "ucsc"


def test_a_naming_mismatch_is_named_even_when_other_contigs_do_not_match(
    tmp_path: Path,
) -> None:
    """The hint fires when *some* contig canonicalises to the query, not when all do.

    The existing check uses a one-contig reference, so `any` and `all` agree on it. With
    more than one contig and `all`, a `chr`-style query against a reference that holds the
    same locus under another spelling falls through to a plain unknown-contig error — which
    sends the reader to look for a missing chromosome instead of a naming difference, the
    one diagnosis the message exists to prevent.
    """
    fa = _write_fasta(tmp_path, {"Chr9": "ACGTACGT", "chr1": "ACGTACGT"})
    with ReferenceGenome(fa) as ref:
        with pytest.raises(ContigNamingError, match="contig-naming mismatch"):
            ref.fetch(_iv("9", 0, 4))
        # A genuinely absent contig still reads as absent.
        with pytest.raises(KeyError, match="unknown contig"):
            ref.fetch(_iv("22", 0, 4))


def test_a_fasta_without_a_trailing_newline_is_not_called_truncated(tmp_path: Path) -> None:
    """The size check excludes the final line terminator, which a FASTA may omit.

    `full_lines = max(-(-rlen // lenc) - 1, 0)` counts the line breaks *inside* the record,
    so the last line is allowed to end without one. Get that arithmetic wrong and a
    perfectly good reference is refused as "replaced or truncated after it was indexed" —
    a refusal that names the wrong cause and tells the reader to rebuild an index that is
    correct.
    """
    body = "ACGTACGTAC\nGGGGTTTTCC\nAAAA"  # three lines, 24 bases, 10 per line

    with_newline = tmp_path / "with_newline.fa"
    with_newline.write_text(f">chr1\n{body}\n")
    with ReferenceGenome(with_newline) as ref:
        assert ref.contig_length("chr1") == 24

    without = tmp_path / "without_newline.fa"
    without.write_text(f">chr1\n{body}")
    with ReferenceGenome(without) as ref:
        assert ref.contig_length("chr1") == 24
        assert str(ref.fetch(_iv("chr1", 20, 24))) == "AAAA", "the last line is readable"


@pytest.mark.filterwarnings("ignore:Index file .* is older than FASTA file:RuntimeWarning")
def test_a_genuinely_truncated_fasta_is_refused_with_both_byte_counts(tmp_path: Path) -> None:
    """The other side: bases the index promises and the file no longer holds.

    The message quotes both numbers, so the reader can see the shortfall rather than take
    "stale index" on trust. A reference silently short of its index returns the wrong bases.
    """
    fasta = tmp_path / "truncated.fa"
    fasta.write_text(">chr1\nACGTACGTAC\nGGGGTTTTCC\nAAAA\n")
    with ReferenceGenome(fasta):
        pass  # index it while it is whole
    whole = fasta.stat().st_size
    fasta.write_bytes(fasta.read_bytes()[:-6])

    with pytest.raises(ReferenceIndexError) as excinfo:
        ReferenceGenome(fasta)
    message = str(excinfo.value)
    assert f"{fasta.stat().st_size} on disk" in message, message
    assert "bytes required" in message
    assert str(whole - 6) in message, "the size it actually has"


@pytest.mark.filterwarnings("ignore:Index file .* is older than FASTA file:RuntimeWarning")
def test_the_required_size_counts_the_line_breaks_inside_the_record(tmp_path: Path) -> None:
    """The size check's arithmetic, at the one byte where a weaker version differs.

    `required = offset + rlen + full_lines * (lenb - lenc)` adds back the newlines that sit
    *between* the record's lines. For this fixture — 24 bases over three 10-base lines after
    a 6-byte header — that is `6 + 24 + 2 * 1 = 32`, which is exactly the file's size without
    its trailing newline.

    Weaken the arithmetic (`full_lines` clamped to 0, or the newline term subtracted or
    divided) and `required` becomes 30. A file short by two bytes then passes, and every read
    through the stale index returns bases shifted by the missing line breaks — silently, which
    is the failure this check exists to prevent. The earlier truncation test drops six bytes,
    enough for the weaker check to catch too, so only the boundary separates them.
    """
    body = "ACGTACGTAC\nGGGGTTTTCC\nAAAA"  # 24 bases, three lines of 10
    fasta = tmp_path / "boundary.fa"
    fasta.write_text(f">chr1\n{body}\n")
    with ReferenceGenome(fasta):
        pass  # index it whole
    whole = fasta.stat().st_size
    assert whole == 33, "the fixture's byte count is load-bearing here"

    # One byte short is the missing trailing newline, which is allowed.
    fasta.write_bytes(fasta.read_bytes()[:-1])
    with ReferenceGenome(fasta) as ref:
        assert ref.contig_length("chr1") == 24

    # Two bytes short is a byte of sequence gone, and must be refused by name.
    fasta.write_bytes(fasta.read_bytes()[:-1])
    assert fasta.stat().st_size == 31
    with pytest.raises(ReferenceIndexError) as excinfo:
        ReferenceGenome(fasta)
    assert "32 bytes required, 31 on disk" in str(excinfo.value), excinfo.value


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (0, 10, "ACGTACGTAC"),  # exactly the contig
        (7, 14, "TACNNNN"),  # overruns the end
        (10, 14, "NNNN"),  # starts exactly at the end
        (12, 16, "NNNN"),  # entirely past the end
        (5, 25, "CGTACNNNNNNNNNNNNNNN"),  # far past it
    ],
)
def test_a_window_past_a_contig_end_is_padded_to_its_requested_width(
    tmp_path: Path, start: int, end: int, expected: str
) -> None:
    """`right_pad = (end - start) - (real_hi - real_lo) - left_pad`.

    A window near a telomere still comes back the width that was asked for, padded with `N`,
    so callers that index into the result by offset stay correct. Everything downstream
    assumes that: the off-target scanner walks the window by position, and the resolver
    reports what fraction of the requested bases were searchable. Get the padding arithmetic
    wrong and the sequence is a different length from the interval that produced it, which
    shifts every offset computed against it.

    Covered at four positions relative to the contig end, including a window that starts
    exactly on it — the case where no real bases are available at all.
    """
    fasta = tmp_path / "pad.fa"
    fasta.write_text(">chr1\nACGTACGTAC\n")  # 10 bases
    with ReferenceGenome(fasta) as ref:
        sequence = str(ref.fetch(_iv("chr1", start, end)))

    assert len(sequence) == end - start, "the result must be as wide as the interval"
    assert sequence == expected
