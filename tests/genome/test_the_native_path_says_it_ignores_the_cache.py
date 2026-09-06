"""When the native index ignores the cache arguments, it must say so.

`FMIndex.build` takes `cache_dir`, `rebuild`, `in_memory`, `occ_rate` and `sa_rate`,
and documents a content-addressed on-disk cache. With the Rust crate built — the
configuration the README recommends for real genomes — the first line dispatches to
`ext.fm_build(str(text))` and **every one of those arguments is dropped**:

    native  type=NativeFmIndex  cache files=[]
    python  type=FMIndex        cache files=['bwt.bin', 'meta.json', 'occ.json', ...]

So a caller who passes `cache_dir=...` (or `search(..., fm_cache_dir=...)`, which is
what threads it down) gets no cache, no error, and no indication — and the index is
rebuilt from scratch on every call, which for a design is once per candidate.

This is the shape this project keeps finding: a real parameter inert on the path most
users run, with a green suite. It is not fixed here — persisting the Rust index is a
feature, not a correction — so the requirement is that the ignoring is *stated*. A
warning is the cheapest thing that makes an inert argument visible, and it fires only
when an argument was actually supplied: the default path must stay silent or it
becomes noise that gets filtered.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.genome.index import FMIndex, native_fm_available

SEQ = "ACGTACGTTTAGGCCATTACGATCGATTACAGGCATCAGCATCAGCATT" * 4

requires_native = pytest.mark.skipif(
    not native_fm_available(), reason="native aforge_native FM-index kernel not built"
)


@requires_native
@pytest.mark.native
@pytest.mark.parametrize(
    "kwargs",
    [
        {"cache_dir": "SENTINEL"},
        {"rebuild": True},
        {"occ_rate": 17},
        {"sa_rate": 9},
    ],
    ids=["cache_dir", "rebuild", "occ_rate", "sa_rate"],
)
def test_a_dropped_argument_warns(tmp_path: Path, kwargs: dict) -> None:
    if kwargs.get("cache_dir") == "SENTINEL":
        kwargs["cache_dir"] = tmp_path
    with pytest.warns(UserWarning, match="native"):
        FMIndex.build(SEQ, **kwargs)


@requires_native
@pytest.mark.native
def test_the_default_call_is_silent(recwarn: pytest.WarningsRecorder) -> None:
    """A warning on every build would be filtered out within a week."""
    FMIndex.build(SEQ)
    assert not [w for w in recwarn if "native" in str(w.message)]


@requires_native
@pytest.mark.native
def test_the_warning_names_the_way_out(tmp_path: Path) -> None:
    """`prefer_native=False` is the caller's remedy, so the warning has to say it."""
    with pytest.warns(UserWarning) as caught:
        FMIndex.build(SEQ, cache_dir=tmp_path)
    assert any("prefer_native" in str(w.message) for w in caught)


def test_the_python_path_still_honours_them(tmp_path: Path) -> None:
    """Not marked `native`: the fallback's cache is the behaviour being contrasted."""
    FMIndex.build(SEQ, cache_dir=tmp_path, prefer_native=False)
    assert list(tmp_path.rglob("meta.json"))


@requires_native
@pytest.mark.native
def test_in_memory_is_satisfied_not_ignored(recwarn: pytest.WarningsRecorder) -> None:
    """The native index *is* in memory, so asking for that is honoured.

    Listing it among the ignored arguments made the warning fire on every native
    scan — `_scan_sequence` always passes `in_memory=True` — which is precisely the
    noise this warning exists not to be.
    """
    FMIndex.build(SEQ, in_memory=True)
    assert not [w for w in recwarn if "native" in str(w.message)]


@requires_native
@pytest.mark.native
def test_a_default_scan_does_not_warn(tmp_path: Path, recwarn: pytest.WarningsRecorder) -> None:
    """The end-to-end shape the previous check is about: a plain search is silent."""
    from alleleforge.genome.reference import ReferenceGenome
    from alleleforge.offtarget.engine import search
    from alleleforge.types.guide import PAM

    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr1\n" + SEQ + "\n")
    search("ACGTACGTTTAGGCCATTAC", PAM(pattern="NGG"), reference=ReferenceGenome(fasta))
    assert not [w for w in recwarn if "native" in str(w.message)]
