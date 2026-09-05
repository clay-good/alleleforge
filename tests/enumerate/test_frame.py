"""Direct tests of the coordinate algebra both enumerators depend on.

`EditFrame` is reached only through `enumerate_prime` and `enumerate_cas9`, and it
is 100% covered that way — by two specific loci each. That is coverage, not
verification: a change to the mapping could keep those loci passing and still be
wrong in general, and every coordinate defect this codebase has produced (a
placement off by an indel's length, a cut index that did not move with its allele)
is exactly that shape.

The oracle is construction rather than arithmetic: build the start genome by
splicing, then walk it against the reference to derive each index's true
reference coordinate independently of anything the frame computes.
"""

from __future__ import annotations

import random

from alleleforge.enumerate._frame import EditFrame
from alleleforge.types.sequence import Strand


def _case(reference: str, rel: int, ref_len: int, carried: str) -> tuple[EditFrame, EditFrame, str]:
    """Return ``(plus frame, reverse frame, start genome)`` for one edit."""
    start_genome = reference[:rel] + carried + reference[rel + ref_len :]
    common = {
        "chrom": "chr1",
        "offset": 0,
        "edit_plus": rel,
        "start_len": len(carried),
        "ref_len": ref_len,
        "span": len(start_genome),
    }
    return EditFrame(**common), EditFrame(**common, reverse=True), start_genome


def test_a_span_clear_of_the_edit_fetches_back_verbatim() -> None:
    """The contract every placement rests on: outside the edit, the map is exact."""
    rng = random.Random(31337)
    for _ in range(400):
        reference = "".join(rng.choice("ACGT") for _ in range(120))
        rel = rng.randrange(20, 100)
        ref_len = rng.randrange(0, 8)
        carried = "".join(rng.choice("ACGT") for _ in range(rng.randrange(0, 8)))
        frame, _reverse, start_genome = _case(reference, rel, ref_len, carried)
        edit_end = rel + len(carried)

        for _probe in range(8):
            lo = rng.randrange(0, max(1, len(start_genome) - 5))
            hi = min(lo + rng.randrange(1, 20), len(start_genome))
            if not (hi <= rel or lo >= edit_end):
                continue  # crosses the edit: a footprint, not an exact span
            interval = frame.interval(lo, hi, Strand.PLUS)
            assert interval is not None
            assert interval.end - interval.start == hi - lo
            assert reference[interval.start : interval.end] == start_genome[lo:hi]


def test_the_reference_map_never_goes_backwards() -> None:
    """A non-monotone map would let an interval invert, which no consumer checks."""
    rng = random.Random(4)
    for _ in range(200):
        reference = "".join(rng.choice("ACGT") for _ in range(60))
        rel = rng.randrange(5, 50)
        frame, _rev, start_genome = _case(
            reference,
            rel,
            rng.randrange(0, 6),
            "".join(rng.choice("ACGT") for _ in range(rng.randrange(0, 6))),
        )
        coords = [frame.coord(i) for i in range(len(start_genome))]
        assert coords == sorted(coords)


def test_the_reverse_frame_is_the_plus_frame_mirrored() -> None:
    """The minus-strand enumeration must not be a second, divergent implementation."""
    rng = random.Random(99)
    for _ in range(200):
        reference = "".join(rng.choice("ACGT") for _ in range(80))
        rel = rng.randrange(10, 60)
        plus, reverse, start_genome = _case(
            reference,
            rel,
            rng.randrange(0, 5),
            "".join(rng.choice("ACGT") for _ in range(rng.randrange(0, 5))),
        )
        span = len(start_genome)
        lo = rng.randrange(0, span - 1)
        hi = min(lo + rng.randrange(1, 15), span)
        mirrored = plus.interval(span - hi, span - lo, Strand.PLUS)
        got = reverse.interval(lo, hi, Strand.PLUS)
        if mirrored is None:
            assert got is None
            continue
        assert got is not None
        assert (got.start, got.end) == (mirrored.start, mirrored.end)
        assert got.strand is Strand.MINUS  # the frame flips it


def test_a_span_inside_inserted_bases_has_no_reference_locus() -> None:
    """Inserted bases the reference does not contain cannot be placed on it."""
    reference = "ACGT" * 20
    rel, ref_len = 30, 0
    carried = "GGGGGGGGGG"  # ten bases the reference has nothing to match
    frame, _rev, _start = _case(reference, rel, ref_len, carried)
    # Wholly inside the insertion, past the zero-width span it replaces.
    assert frame.interval(rel + 1, rel + len(carried), Strand.PLUS) is None
    # Straddling its 5' boundary, the span still has the bases before it.
    straddle = frame.interval(rel - 4, rel + len(carried), Strand.PLUS)
    assert straddle is not None
    assert (straddle.start, straddle.end) == (rel - 4, rel)


def test_an_allele_with_a_reference_span_always_places() -> None:
    """A substitution or deletion replaces real bases, so it always has a locus."""
    reference = "ACGT" * 20
    for ref_len, carried in ((1, "A"), (5, "A"), (3, "TTT"), (4, "")):
        frame, _rev, _start = _case(reference, 30, ref_len, carried)
        interval = frame.interval(30, 30 + max(1, len(carried)), Strand.PLUS)
        assert interval is not None, f"ref_len={ref_len} carried={carried!r}"
        assert interval.end > interval.start


def test_the_identity_frame_is_a_plain_offset() -> None:
    """A window carrying no length change must map exactly as an offset would."""
    frame = EditFrame.identity(chrom="chr1", offset=1000, span=50)
    interval = frame.interval(10, 30, Strand.PLUS)
    assert interval is not None
    assert (interval.start, interval.end) == (1010, 1030)
    assert [frame.coord(i) for i in (0, 25, 49)] == [1000, 1025, 1049]
