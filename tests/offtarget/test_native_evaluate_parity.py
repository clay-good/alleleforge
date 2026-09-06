"""Native per-anchor evaluation parity: the Rust kernel matches the Python fallback.

`_evaluate` is the per-anchor entry point of the off-target scan — 500,000 calls over
2 Mb — and it previously did the ungapped comparison in Python and crossed the FFI
boundary twice more for the two bulge directions. Moving the whole decision into Rust
removes a million boundary crossings as well as the interpreter loop: **a 2 Mb scan
goes 1.184s -> 0.869s, 27%**, measured as three interleaved A/B pairs so the figure is
not one run against another run's weather.

The project's contract for every native kernel is that an unbuilt crate changes the
*speed* of a run and not its results, so this asserts the two paths agree exactly. A
different alignment here is a different reported off-target site.

Writing the port forced two decisions the Python had never made, which is what porting
is for. Both were off-contract — the scan only reports a PAM it found *inside* the
sequence — and in both the Python's accidental answer was worse than an error:

* `pam_at` past the end of `seq`: Python sliced a short window and then raised
  `ValueError` from a `zip(..., strict=True)` three frames down.
* the same, with an **empty spacer**: every slice is legally empty, so the ungapped
  comparison returned a *zero-mismatch hit at a coordinate outside the sequence* — the
  most confident possible answer about a protospacer that does not exist.

Both paths now return `None`, which is what lets the parity claim hold everywhere
rather than only on the inputs the caller happens to produce. The randomized generator
below draws `pam_at` past the end and spacers of length 0 deliberately: with the
generator ranges the first draft used (`n >= 2`, `pam_at <= len(seq)`), 200,000 cases
passed and both defects were invisible.
"""

from __future__ import annotations

import random

import pytest

from alleleforge.offtarget._search import (
    _evaluate,
    _native_evaluate_available,
    _python_evaluate,
)

requires_native = pytest.mark.skipif(
    not _native_evaluate_available(), reason="native aforge_native evaluate kernel not built"
)

#: Shapes the randomized generator does not reliably produce, each pinning a decision.
_EDGE_CASES = [
    ("ACGT", "", 0, 1, 1, 1),
    ("ACGT", "ACGT", 4, 0, 0, 0),
    ("ACGT", "ACGT", 4, 0, 1, 1),
    ("ACGT", "AAACGT", 6, 0, 1, 1),
    ("ACGT", "ACGTT", 5, 0, 1, 0),
    ("ACGT", "ACG", 3, 0, 0, 1),
    ("A", "AA", 2, 0, 1, 1),
    ("AC", "A", 1, 0, 0, 1),
    ("N", "N", 1, 0, 0, 0),
    ("ACGT", "NNNN", 4, 4, 1, 1),
    ("ACGTACGTACGTACGTACGT", "T" * 40, 40, 4, 1, 1),
    # Off contract, and the two shapes the port had to decide about.
    ("ACGT", "ACGT", 99, 4, 1, 1),
    ("", "ACGT", 0, 0, 1, 1),
    ("", "CNATGT", 9, 1, 0, 1),
    ("", "", 2, 2, 1, 0),
]


def _both(spacer: str, seq: str, pam_at: int, mm: int, dna: int, rna: int) -> tuple:
    kwargs = {"max_mm": mm, "dna_bulges": dna, "rna_bulges": rna}
    return (
        _evaluate(spacer, seq, pam_at, 3, **kwargs),
        _python_evaluate(spacer, seq, pam_at, 3, **kwargs),
    )


@requires_native
@pytest.mark.native
def test_the_dispatcher_is_actually_using_the_native_kernel() -> None:
    """A floor: without this the parity checks below could be Python against Python."""
    from alleleforge.offtarget._search import _NATIVE_EVALUATE

    assert _NATIVE_EVALUATE is not None


@requires_native
@pytest.mark.native
@pytest.mark.parametrize("case", _EDGE_CASES, ids=lambda c: f"{c[0]!r}-{c[1]!r}-{c[2]}")
def test_hand_written_shapes_agree(case: tuple) -> None:
    native, python = _both(*case)
    assert native == python


@requires_native
@pytest.mark.native
def test_randomized_shapes_agree() -> None:
    """Deliberately including `n == 0` and `pam_at` beyond the sequence.

    The first draft of this generator produced neither, and passed 200,000 cases over
    two implementations that disagreed on both.
    """
    rng = random.Random(11)
    for _ in range(20_000):
        n = rng.randint(0, 8)
        spacer = "".join(rng.choice("ACGTN") for _ in range(n))
        seq = "".join(rng.choice("ACGTN") for _ in range(rng.randint(0, 24)))
        pam_at = rng.randint(0, len(seq) + 3)
        native, python = _both(
            spacer, seq, pam_at, rng.randint(0, 4), rng.randint(0, 1), rng.randint(0, 1)
        )
        assert native == python, (spacer, seq, pam_at)


@pytest.mark.parametrize(
    "case",
    [c for c in _EDGE_CASES if c[2] > len(c[1])],
    ids=lambda c: f"{c[0]!r}-pam_at-{c[2]}",
)
def test_the_python_path_refuses_an_out_of_range_pam(case: tuple) -> None:
    """Not marked `native`: this is the Python path's own contract, crate or no crate.

    It used to raise `ValueError`, or — for an empty spacer — return a hit.
    """
    spacer, seq, pam_at, mm, dna, rna = case
    assert (
        _python_evaluate(spacer, seq, pam_at, 3, max_mm=mm, dna_bulges=dna, rna_bulges=rna) is None
    )
