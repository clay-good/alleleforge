"""Native FM-index parity: the Rust ``bwt`` kernel matches the Python fallback.

The availability invariant runs everywhere; the parity tests are marked
``native`` and skip unless the ``aforge_native`` crate is built with the FM-index
kernels (CI builds it in a dedicated job; ``maturin develop`` builds it locally).
They assert the native index returns **byte-identical** results to the proven
pure-Python implementation, so the optimization can never silently diverge.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from alleleforge import _native
from alleleforge.genome.index import FMIndex, native_fm_available
from alleleforge.types.guide import PAM

_TEXTS = [
    "AAAGGGCCCTGGAAGGTTGG",
    "ACGTNNNNACGT",
    "ACGTACGT",
    "GACCATGCAACCTTGAACGTACGTAACGTTGG",
    "N" * 5 + "ACGTACGTACGT",
]
_PATS = ["A", "C", "GG", "AGG", "CCC", "TTGG", "ACGT", "N", "NN", "ZZZ", "ACGTA"]

requires_native = pytest.mark.skipif(
    not native_fm_available(), reason="native aforge_native FM-index kernels not built"
)


def test_native_fm_available_reflects_built_kernels() -> None:
    # Always-on invariant: availability is True iff the crate exposes fm_locate.
    ext = getattr(_native, "_ext", None)
    expected = _native.NATIVE_AVAILABLE and ext is not None and hasattr(ext, "fm_locate")
    assert native_fm_available() is expected


def _python_index(text: str, tmp_path: Path) -> FMIndex:
    return FMIndex.build(text, prefer_native=False, cache_dir=tmp_path)


@requires_native
@pytest.mark.native
@pytest.mark.parametrize("text", _TEXTS)
def test_native_matches_python_count_and_locate(text: str, tmp_path: Path) -> None:
    native = FMIndex.build(text, prefer_native=True)
    py = _python_index(text, tmp_path)
    assert native.content_hash == py.content_hash
    assert native.length == py.length
    for pat in _PATS:
        assert native.count(pat) == py.count(pat), (text, pat)
        assert native.locate(pat) == py.locate(pat), (text, pat)
    native.close()
    py.close()


@requires_native
@pytest.mark.native
@pytest.mark.parametrize("text", _TEXTS)
def test_native_matches_python_pam_sites(text: str, tmp_path: Path) -> None:
    pam = PAM(pattern="NGG")
    native = FMIndex.build(text, prefer_native=True)
    py = _python_index(text, tmp_path)

    def tuples(idx: FMIndex) -> list[tuple[int, int, int, str]]:
        return [
            (h.protospacer_start, h.pam_start, h.pam_end, h.pam_sequence)
            for h in idx.pam_sites(pam, 3)
        ]

    assert tuples(native) == tuples(py)
    native.close()
    py.close()


@requires_native
@pytest.mark.native
def test_native_rejects_empty_and_bad_alphabet() -> None:
    with pytest.raises(ValueError, match="empty"):
        FMIndex.build("", prefer_native=True)
    with pytest.raises(ValueError, match="ACGTN"):
        FMIndex.build("ACGTX", prefer_native=True)


@requires_native
@pytest.mark.native
def test_native_index_is_a_context_manager() -> None:
    with FMIndex.build("ACGTACGT", prefer_native=True) as idx:
        assert idx.count("ACGT") == 2
    idx.close()  # idempotent / no-op after the context exits


# Large and low-complexity inputs: poly-A / poly-N runs and tandem repeats are
# exactly where the old O(n^2 log n) direct sort degraded and where a
# prefix-doubling suffix-array bug would surface. The unique sentinel keeps the
# suffix array unique, so native must still match the Python fallback exactly.
_STRESS_TEXTS = [
    "A" * 300,
    "AC" * 150,
    "ACGT" * 80,
    "N" * 60 + "ACGT" * 40,
    "GGGG" + "A" * 100 + "TTTT" + "C" * 100,
]


@requires_native
@pytest.mark.native
@pytest.mark.parametrize("text", _STRESS_TEXTS)
def test_native_matches_python_on_low_complexity(text: str, tmp_path: Path) -> None:
    native = FMIndex.build(text, prefer_native=True)
    py = _python_index(text, tmp_path)
    assert native.content_hash == py.content_hash
    for pat in ("A", "AA", "AAA", "ACGT", "GGGG", "NN", "ACGTACGT", "TTTT", "CCC"):
        assert native.count(pat) == py.count(pat), (text[:8], pat)
        assert native.locate(pat) == py.locate(pat), (text[:8], pat)
    native.close()
    py.close()


def _ground_truth_sa(text: str) -> list[int]:
    """The suffix array of ``text`` + sentinel by the O(n^2 log n) direct sort."""
    data = text.upper() + "\x00"
    return sorted(range(len(data)), key=lambda i: data[i:])


# SA-IS edge cases live in low-complexity and repeat structure: all-same runs,
# alternating S/L runs, tandem repeats, and the textbook hard inputs.
_SA_TEXTS = [
    "A",
    "N",
    "AC",
    "ACGT",
    "A" * 200,
    "N" * 200,
    "AC" * 100,
    "ACGT" * 64,
    "GGGG" + "A" * 50 + "TTTT" + "C" * 50,
    "ATATATATGCGCGC",
    "AAAACAAAAC" * 10,
    "ACACGTGTACAC",  # mapped 'mississippi'-like alternation
]


@requires_native
@pytest.mark.native
@pytest.mark.parametrize("text", _SA_TEXTS)
def test_native_sais_matches_direct_sort(text: str) -> None:
    # The linear-time SA-IS build is byte-identical to the ground-truth direct sort
    # (the unique sentinel makes every suffix distinct, so the SA is unique).
    assert list(_native._ext.fm_suffix_array(text)) == _ground_truth_sa(text)


@requires_native
@pytest.mark.native
def test_native_sais_matches_direct_sort_fuzz() -> None:
    rng = random.Random(12345)
    for _ in range(500):
        alphabet = rng.choice(["AC", "ACG", "ACGT", "ACGTN", "A", "AN"])
        text = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 60)))
        assert list(_native._ext.fm_suffix_array(text)) == _ground_truth_sa(text), text


@requires_native
@pytest.mark.native
def test_native_matches_python_on_random_long_inputs() -> None:
    rng = random.Random(20240501)
    for _ in range(20):
        # bias toward repeats so the suffix array sees long shared prefixes
        unit = "".join(rng.choice("ACGT") for _ in range(rng.randint(1, 4)))
        text = (unit * rng.randint(20, 120))[: rng.randint(50, 400)]
        text += "".join(rng.choice("ACGTN") for _ in range(rng.randint(0, 40)))
        native = FMIndex.build(text, prefer_native=True)
        import tempfile

        py = FMIndex.build(text, prefer_native=False, cache_dir=tempfile.mkdtemp())
        assert native.content_hash == py.content_hash
        for _ in range(10):
            j = rng.randint(0, len(text) - 1)
            pat = text[j : j + rng.randint(1, 8)]
            assert native.locate(pat) == py.locate(pat), (text[:12], pat)
        native.close()
        py.close()
