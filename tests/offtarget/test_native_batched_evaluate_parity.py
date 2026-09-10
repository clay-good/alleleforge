"""The batched kernel must return exactly what the per-anchor one returns, filtered.

`evaluate_anchors` takes a whole scan's anchor list across the FFI boundary once and
returns only the anchors that scored. The scan keeps two hits out of 250,000 anchors on a
2 Mb contig, so every rejected anchor was a Python frame, an argument tuple and a crossing
spent on a discard — and removing them is worth nothing at all if the surviving hits are
not identical, because a different alignment here is a different reported off-target site.

Same contract as every other kernel in this crate: an extension that predates the batched
function (or an install with no crate at all) changes the *speed* of a scan and not its
results, so the two paths are compared exactly, on shapes drawn to include the ones the
per-anchor parity test had to decide about — an anchor past the end of the sequence, an
empty spacer, an all-`N` window.
"""

from __future__ import annotations

import random

import pytest

from alleleforge.offtarget import _search
from alleleforge.types.guide import PAM

requires_batched = pytest.mark.skipif(
    _search._NATIVE_EVALUATE_MANY is None,
    reason="native aforge_native evaluate_anchors kernel not built",
)


def _per_anchor(spacer: str, seq: str, anchors: list[int], budget: tuple[int, int, int]) -> list:
    max_mm, dna_bulges, rna_bulges = budget
    evaluate = _search._anchor_evaluator(
        spacer, seq, 3, max_mm=max_mm, dna_bulges=dna_bulges, rna_bulges=rna_bulges
    )
    found = []
    for pam_at in anchors:
        result = evaluate(pam_at)
        if result is not None:
            found.append((pam_at, *result))
    return found


@pytest.mark.native
@requires_batched
def test_randomized_scans_agree() -> None:
    rng = random.Random(20240501)
    for _ in range(300):
        n = rng.randint(0, 22)
        spacer = "".join(rng.choice("ACGTN") for _ in range(n))
        seq = "".join(rng.choice("ACGTN") for _ in range(rng.randint(1, 120)))
        budget = (rng.randint(0, 5), rng.randint(0, 1), rng.randint(0, 1))
        # Anchors past the end included on purpose: the per-anchor port had to decide
        # what those mean, and a batched kernel that decided differently would be a
        # divergence only a real genome's edge would reveal.
        anchors = sorted({rng.randint(0, len(seq) + 2) for _ in range(12)})
        batched = [
            tuple(row) for row in _search._NATIVE_EVALUATE_MANY(spacer, seq, anchors, *budget)
        ]
        assert batched == _per_anchor(spacer, seq, anchors, budget), (spacer, seq, anchors, budget)


@pytest.mark.native
@requires_batched
def test_a_whole_strand_scan_is_unchanged_by_the_batching() -> None:
    """End to end: the tuples `_scan_one_strand` returns, batched and per-anchor."""
    rng = random.Random(7)
    spacer = "GACCATGCAACCTTGAACGT"
    seq = "".join(rng.choice("ACGT") for _ in range(50_000)) + spacer + "TGG"
    pam = PAM(pattern="NGG")
    kw = {"max_mm": 4, "dna_bulges": 1, "rna_bulges": 1}

    batched = _search._scan_one_strand(spacer, seq, pam, **kw)
    anchors = [
        match.start()
        for match in _search._pam_anchor_scanner(pam.pattern).finditer(seq, len(spacer) - 1)
    ]
    per_anchor = [
        (start, pam_at, seq[pam_at : pam_at + 3], mm, dnab, rnab, a_spacer, a_target)
        for pam_at, start, mm, dnab, rnab, a_spacer, a_target in _per_anchor(
            spacer, seq, anchors, (4, 1, 1)
        )
        if seq.find("N", start, pam_at) == -1
    ]
    assert batched == per_anchor
    assert batched, "the fixture must produce a hit or this proves nothing"
