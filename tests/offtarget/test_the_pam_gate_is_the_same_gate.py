"""Finding the PAM anchors with a regex must admit exactly the anchors the loop did.

`_scan_one_strand` used to ask "does the window at this anchor match the PAM?" once per
position per strand, in Python: slice three characters, look them up in a memo, and
`continue` on a miss. At the default budget the k-mer prefilter does not apply —
`seed_length(20, 4 + 1 + 1)` falls below `MIN_SELECTIVE_K`, so `_seed_filter` returns
``None`` and every anchor reached that check. For a 2 Mb scan that is four million slices
and four million dict lookups before a single alignment is evaluated.

    2 Mb scan (alternating, three runs each)   before 0.36/0.51/0.56s   after 0.15/0.23/0.21s
    `aforge offtarget` over 20 Mb              before 6.70/5.65/5.37s   after 3.64/3.17/2.84s

with byte-identical JSON.

"Does this window match an IUPAC pattern" is a regular question, so the regex engine can
answer it for the whole sequence in C. Two things make the translation exact rather than
approximate, and both are what this file pins:

* Each pattern code becomes the character class of the bases it admits. Every
  `IUPAC_EXPAND` value is a set of **concrete** bases — ``N`` expands to ``ACGT``, not to
  ``ACGTN`` — so no class can name ``N``, and the exclusion the old code wrote out
  separately (`"N" not in pam_seq`) falls out instead of being a second test to remember.
  That is a property of a table in another module, so it is pinned here rather than
  assumed: an expansion that grew to include ``N`` would put ``N`` in a class and quietly
  widen every hit set, which is not an error anything would raise.
* The scan is a **lookahead**. PAM windows overlap — ``AGGG`` holds an ``NGG`` match at 0
  and another at 1 — and a consuming match would resume past the first and lose the
  second. This is the failure that would not raise: fewer anchors, fewer sites, a guide
  that looks safer than it is.

The differential test is the one that matters. A hand-written equivalence argument about
a regex is exactly the kind of reasoning that is wrong in one corner, so the old loop is
reproduced verbatim below and both are run over the same inputs.
"""

from __future__ import annotations

import itertools
import random

import pytest

from alleleforge.offtarget._search import (
    _CONCRETE_BASES,
    _evaluate,
    _pam_anchor_scanner,
    _scan_one_strand,
    _seed_filter,
)
from alleleforge.types.guide import PAM
from alleleforge.types.sequence import IUPAC_EXPAND

#: Patterns worth checking: the ones the project ships or documents, plus degenerate
#: codes that are not simply "N or a literal" — a class-per-code translation that quietly
#: mishandled `R`/`Y`/`V` would pass a test that only ever saw `NGG`.
_PATTERNS = ("NGG", "NG", "NGA", "NGCG", "NNGRRT", "TTTV", "NNNNGATT", "YG", "BDHV", "SWKM")


def _scan_the_old_way(
    spacer: str,
    seq: str,
    pam: PAM,
    *,
    max_mm: int,
    dna_bulges: int,
    rna_bulges: int,
    seed: bool = True,
) -> list[tuple[int, int, str, int, int, int, str, str]]:
    """The per-anchor loop as it stood, kept as the oracle for the differential test."""
    pam_len = len(pam.pattern)
    n = len(spacer)
    covered = (
        _seed_filter(spacer, seq, max_mm=max_mm, dna_bulges=dna_bulges, rna_bulges=rna_bulges)
        if seed
        else None
    )
    hits: list[tuple[int, int, str, int, int, int, str, str]] = []
    pam_ok: dict[str, bool] = {}
    for pam_at in range(len(spacer) - 1, len(seq) - pam_len + 1):
        if covered is not None:
            lo = max(0, pam_at - (n + 1))
            if covered[pam_at] - covered[lo] == 0:
                continue
        pam_seq = seq[pam_at : pam_at + pam_len]
        ok = pam_ok.get(pam_seq)
        if ok is None:
            ok = "N" not in pam_seq and pam.matches(pam_seq)
            pam_ok[pam_seq] = ok
        if not ok:
            continue
        result = _evaluate(
            spacer,
            seq,
            pam_at,
            pam_len,
            max_mm=max_mm,
            dna_bulges=dna_bulges,
            rna_bulges=rna_bulges,
        )
        if result is None:
            continue
        start, mm, dnab, rnab, a_spacer, a_target = result
        if "N" in seq[start:pam_at]:
            continue
        hits.append((start, pam_at, pam_seq, mm, dnab, rnab, a_spacer, a_target))
    return hits


@pytest.mark.parametrize("pattern", _PATTERNS)
def test_the_scanner_admits_exactly_the_windows_pam_matches_does(pattern: str) -> None:
    """Exhaustive over every window the sanitized alphabet can produce."""
    pam = PAM(pattern=pattern)
    scanner = _pam_anchor_scanner(pattern)
    for window in itertools.product("ACGTN", repeat=len(pattern)):
        text = "".join(window)
        expected = "N" not in text and pam.matches(text)
        match = scanner.match(text)
        assert (match is not None) == expected, text
        if match is not None:
            assert match.group(1) == text


def test_no_expansion_admits_an_unknown_base() -> None:
    """The property the character classes rest on, pinned where it is relied upon.

    `_scan_one_strand` no longer tests `"N" not in pam_seq`; it relies on no pattern code
    admitting ``N``. If `IUPAC_EXPAND` ever mapped a code to a set containing ``N``, the
    scan would start nominating sites over unknown bases with nothing raising.
    """
    assert all(expansion <= _CONCRETE_BASES for expansion in IUPAC_EXPAND.values()), (
        "a PAM character class could name N"
    )


def test_overlapping_pam_windows_are_all_found() -> None:
    """The lookahead's reason for existing, as a case rather than as an argument."""
    scanner = _pam_anchor_scanner("NGG")
    assert [m.start() for m in scanner.finditer("AGGG")] == [0, 1]


@pytest.mark.parametrize("pattern", _PATTERNS)
def test_the_scan_returns_what_the_per_anchor_loop_returned(pattern: str) -> None:
    """Same hits, in the same order, over sequences that include Ns and short contigs."""
    pam = PAM(pattern=pattern)
    rng = random.Random(f"pam-gate-{pattern}")
    for _ in range(12):
        alphabet = rng.choice(["ACGT", "ACGTN", "ACGTNN"])
        seq = "".join(rng.choice(alphabet) for _ in range(rng.choice([25, 40, 120, 600])))
        spacer = "".join(rng.choice("ACGT") for _ in range(rng.choice([18, 20, 23])))
        for max_mm, dna_bulges, rna_bulges, seed in (
            (4, 1, 1, True),  # the default budget: the prefilter does not apply
            (2, 0, 0, True),
            (0, 0, 0, True),
            (3, 1, 0, False),
            (1, 1, 1, True),
        ):
            budget = {
                "max_mm": max_mm,
                "dna_bulges": dna_bulges,
                "rna_bulges": rna_bulges,
                "seed": seed,
            }
            assert _scan_one_strand(spacer, seq, pam, **budget) == _scan_the_old_way(
                spacer, seq, pam, **budget
            ), (pattern, budget, seq, spacer)


def test_a_sequence_shorter_than_the_anchor_window_yields_nothing() -> None:
    """The old `range(len(spacer) - 1, len(seq) - pam_len + 1)` was empty here; the
    scanner's `pos` argument and its need for `pam_len` characters must agree."""
    pam = PAM(pattern="NGG")
    assert (
        _scan_one_strand(
            "ACGTACGTACGTACGTACGT", "AGGTGG", pam, max_mm=4, dna_bulges=1, rna_bulges=1
        )
        == []
    )
