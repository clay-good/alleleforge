"""Tests for the pure-Python FM-index fallback: search, PAM anchoring, cache."""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.genome import index as index_mod
from alleleforge.genome.index import FMIndex
from alleleforge.types.guide import PAM

_TEXT = "AAAGGGCCCTGGAAGGTTGG"


@pytest.fixture(autouse=True)
def _force_python_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin this module to the pure-Python FM-index it tests.

    The native crate, when built, transparently takes over ``FMIndex.build``;
    these fallback tests force the Python path so they are deterministic whether
    or not ``aforge_native`` is installed. Native/Python parity is covered
    separately in ``test_native.py``.
    """
    monkeypatch.setattr(index_mod, "native_fm_available", lambda: False)


def _naive_locate(text: str, pat: str) -> list[int]:
    return [i for i in range(len(text) - len(pat) + 1) if text[i : i + len(pat)] == pat]


@pytest.mark.parametrize("pat", ["A", "GG", "AGG", "CCC", "TTGG", "ACGT"])
def test_count_matches_naive(tmp_path: Path, pat: str) -> None:
    # naive locate counts overlapping occurrences, matching the FM-index.
    with FMIndex.build(_TEXT, cache_dir=tmp_path) as idx:
        assert idx.count(pat) == len(_naive_locate(_TEXT, pat))


def test_count_empty_pattern_is_zero(tmp_path: Path) -> None:
    with FMIndex.build(_TEXT, cache_dir=tmp_path) as idx:
        assert idx.count("") == 0


@pytest.mark.parametrize("pat", ["A", "GG", "AGG", "CCC", "TTGG", "ZZZ"])
def test_locate_matches_naive(tmp_path: Path, pat: str) -> None:
    with FMIndex.build(_TEXT, cache_dir=tmp_path) as idx:
        assert idx.locate(pat) == _naive_locate(_TEXT, pat)


def test_locate_empty_pattern_is_empty(tmp_path: Path) -> None:
    with FMIndex.build(_TEXT, cache_dir=tmp_path) as idx:
        assert idx.locate("") == []


def test_mmap_and_in_memory_agree(tmp_path: Path) -> None:
    idx_mm = FMIndex.build(_TEXT, cache_dir=tmp_path)
    idx_mem = FMIndex.build(_TEXT, cache_dir=tmp_path, in_memory=True)
    try:
        for pat in ("GG", "AGG", "CCC", "TTGG"):
            assert idx_mm.locate(pat) == idx_mem.locate(pat)
        assert idx_mem._mm is None  # eager load keeps no memory map
        assert idx_mm._mm is not None
    finally:
        idx_mm.close()
        idx_mem.close()


def test_pam_sites_match_naive(tmp_path: Path) -> None:
    pam = PAM(pattern="NGG")
    spacer_len = 3
    with FMIndex.build(_TEXT, cache_dir=tmp_path) as idx:
        hits = idx.pam_sites(pam, spacer_len)
        got = {(h.protospacer_start, h.pam_start) for h in hits}
    expected = {
        (p - spacer_len, p)
        for p in range(len(_TEXT) - 2)
        if pam.matches(_TEXT[p : p + 3]) and p - spacer_len >= 0
    }
    assert got == expected
    # every hit carries the concrete PAM it matched, satisfying the pattern
    with FMIndex.build(_TEXT, cache_dir=tmp_path) as idx:
        for h in idx.pam_sites(pam, spacer_len):
            assert pam.matches(h.pam_sequence)
            assert h.pam_end - h.pam_start == 3


def test_content_addressed_cache_is_reused(tmp_path: Path) -> None:
    idx = FMIndex.build(_TEXT, cache_dir=tmp_path)
    meta = tmp_path / idx.content_hash / "meta.json"
    idx.close()
    assert meta.exists()
    mtime = meta.stat().st_mtime_ns
    idx2 = FMIndex.build(_TEXT, cache_dir=tmp_path)
    idx2.close()
    assert idx2.content_hash == idx.content_hash
    assert meta.stat().st_mtime_ns == mtime  # not rebuilt


def test_different_text_different_hash(tmp_path: Path) -> None:
    a = FMIndex.build("ACGTACGT", cache_dir=tmp_path)
    b = FMIndex.build("ACGTACGA", cache_dir=tmp_path)
    try:
        assert a.content_hash != b.content_hash
    finally:
        a.close()
        b.close()


def test_rebuild_flag_forces_rebuild(tmp_path: Path) -> None:
    idx = FMIndex.build(_TEXT, cache_dir=tmp_path)
    idx.close()
    idx2 = FMIndex.build(_TEXT, cache_dir=tmp_path, rebuild=True)
    try:
        assert idx2.count("GG") == len(_naive_locate(_TEXT, "GG"))
    finally:
        idx2.close()


def test_build_rejects_empty(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="empty"):
        FMIndex.build("", cache_dir=tmp_path)


def test_build_rejects_bad_alphabet(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="ACGTN"):
        FMIndex.build("ACGTX", cache_dir=tmp_path)


def test_size_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(index_mod, "SIZE_WARN_THRESHOLD", 4)
    with pytest.warns(UserWarning, match="multi-gigabyte"):
        FMIndex.build("ACGTACGT", cache_dir=tmp_path).close()


def test_close_is_idempotent(tmp_path: Path) -> None:
    idx = FMIndex.build(_TEXT, cache_dir=tmp_path)
    idx.close()
    idx.close()  # no error on second close


def test_indexes_sequence_with_n(tmp_path: Path) -> None:
    with FMIndex.build("ACGTNNNNACGT", cache_dir=tmp_path) as idx:
        assert idx.locate("ACGT") == [0, 8]
        assert idx.count("N") == 4


def test_verify_passes_on_clean_index(tmp_path: Path) -> None:
    with FMIndex.build(_TEXT, cache_dir=tmp_path) as idx:
        idx.verify()  # reconstructs the text from the BWT and matches its content hash


def test_verify_detects_corrupted_index(tmp_path: Path) -> None:
    import hashlib

    from alleleforge.genome.index import FMIndexIntegrityError

    good = FMIndex.build(_TEXT, cache_dir=tmp_path, in_memory=True)
    good.verify()  # sanity: a fresh index verifies
    cache = tmp_path / hashlib.sha256(_TEXT.encode()).hexdigest()
    bwt = (cache / "bwt.bin").read_bytes()
    # Flip one BWT byte so reconstruction diverges from the recorded content hash.
    (cache / "bwt.bin").write_bytes((b"C" if bwt[:1] != b"C" else b"A") + bwt[1:])
    bad = FMIndex.load(cache, in_memory=True)
    with pytest.raises(FMIndexIntegrityError, match="integrity check"):
        bad.verify()
