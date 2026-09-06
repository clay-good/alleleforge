"""A corrupted FM-index cache must not be loaded and queried.

`FMIndex.build` writes a content-addressed cache and `load` reads it back. The cache
directory is named for the sequence hash, so a *directory* that is wrong is caught —
and a *file inside a correctly named directory* was not checked at all:

    clean     : count(ACGTACGT) = 6   locate = [0, 49, 98, 147]
    truncated : loaded without complaint; count = 0   locate = []
    tampered  : loaded without complaint; count = 5   locate = [98, 147, 165, 196]

The truncation is the realistic one — an interrupted build, a full disk — and it is the
worse of the two in this tool: zero hits renders as "0 site(s), specificity 1.000", the
most reassuring output the system can produce, from an index that has lost half its
BWT. The one-byte tamper is worse in kind: it drops a real occurrence *and* reports two
positions (165, 196) that are not occurrences at all, so a scan nominates off-target
loci that do not exist.

`verify()` catches both. It reconstructs the text from the BWT and re-hashes it, and
its docstring says a corrupted cache "fails closed rather than serving wrong locations"
— but nothing in `src/` calls it, so it did neither. It is `O(n)`, which over hg38 is
minutes, so calling it on every load is not the answer.

What is: the structural facts `meta.json` already records can be checked in constant
time. A BWT whose length disagrees with the recorded one, or a `c_table` whose counts
do not sum to it, is corrupt without reconstructing anything. That catches truncation
and a mangled `meta.json` for free; `verify()` remains the deliberate, opt-in check for
same-length tampering, and is now the documented way to get it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alleleforge.genome.index import FMIndex, FMIndexIntegrityError

SEQ = "ACGTACGTTTAGGCCATTACGATCGATTACAGGCATCAGCATCAGCATT" * 6


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    """Build a Python-path index and return its content-addressed directory."""
    FMIndex.build(SEQ, cache_dir=tmp_path, prefer_native=False)
    return next(p.parent for p in tmp_path.rglob("meta.json"))


def test_the_clean_cache_answers_correctly(cache: Path) -> None:
    """The premise: without a floor here, every check below could pass vacuously."""
    fm = FMIndex.load(cache)
    assert fm.count("ACGTACGT") == 6
    assert sorted(fm.locate("ACGTACGT"))[:4] == [0, 49, 98, 147]


def test_a_truncated_bwt_is_refused(cache: Path) -> None:
    """Half a BWT found zero occurrences, which reads as a spotless guide."""
    bwt = cache / "bwt.bin"
    data = bwt.read_bytes()
    bwt.write_bytes(data[: len(data) // 2])
    with pytest.raises(FMIndexIntegrityError, match="length"):
        FMIndex.load(cache)


def test_an_over_long_bwt_is_refused(cache: Path) -> None:
    """Appended bytes are as wrong as missing ones, and as cheap to notice."""
    bwt = cache / "bwt.bin"
    bwt.write_bytes(bwt.read_bytes() + b"ACGT")
    with pytest.raises(FMIndexIntegrityError, match="length"):
        FMIndex.load(cache)


@pytest.mark.parametrize("mangle", ["first-nonzero", "out-of-range", "out-of-order"])
def test_a_mangled_c_table_is_refused(cache: Path, mangle: str) -> None:
    """`meta.json` can rot too, and its offsets must still describe the BWT.

    `c_table[c]` is the first *row* of `c` in the sorted rotations — a cumulative
    offset, not a count. The first version of the check summed them and rejected the
    clean fixture, which is why the three mangles below are each a violation of the
    real invariant rather than of an invented one.
    """
    meta_path = cache / "meta.json"
    meta = json.loads(meta_path.read_text())
    keys = sorted(meta["c_table"])
    if mangle == "first-nonzero":
        meta["c_table"][keys[0]] = 3
    elif mangle == "out-of-range":
        meta["c_table"][keys[-1]] = meta["length"] + 10
    else:
        meta["c_table"][keys[1]], meta["c_table"][keys[-1]] = (
            meta["c_table"][keys[-1]],
            meta["c_table"][keys[1]],
        )
    meta_path.write_text(json.dumps(meta))
    with pytest.raises(FMIndexIntegrityError, match="c_table"):
        FMIndex.load(cache)


def test_same_length_tampering_still_needs_verify(cache: Path) -> None:
    """The constant-time checks are honest about what they do not cover.

    A flipped byte keeps every structural fact intact, so it loads — and answers
    wrongly, including positions that are not occurrences. `verify()` is what catches
    it, and the point of this test is that the cheap check does not pretend to.
    """
    bwt = cache / "bwt.bin"
    data = bytearray(bwt.read_bytes())
    data[5] = ord("T") if data[5] != ord("T") else ord("A")
    bwt.write_bytes(bytes(data))

    fm = FMIndex.load(cache)  # loads: nothing structural is wrong
    assert sorted(fm.locate("ACGTACGT")) != [0, 49, 98, 147]
    with pytest.raises(FMIndexIntegrityError):
        fm.verify()
