"""Where SpCas9 cuts, measured from a genome, on both strands.

The pegRNA's whole geometry hangs off the nick: the PBS anneals to the 3' end the nick
creates, and the RTT is written from it. A one-base error there is not a smaller edit — it
is a different edit, written from the wrong 3' end, and every number in the report is
computed about the wrong reagent. Nothing else about the run would look wrong.

SpCas9 cuts between protospacer positions 17 and 18, three bases 5' of the PAM. Stated in
genomic coordinates that is one arithmetic on each strand, which is exactly where a sign
error lives:

    plus  : protospacer [s, e), PAM at [e, e+3)   ->  nick between e-4 and e-3, i.e. e-3
    minus : protospacer [s, e), PAM at [s-3, s)   ->  nick between s+2 and s+3, i.e. s+2

Both are "three bases from the PAM", counted in the direction that strand reads. The test
builds a contig with the protospacer at a known offset and requires the reported
`nick_site` to be those expressions, so a shift anywhere in variant resolution, protospacer
placement or nick arithmetic fails here rather than shipping.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome

_START, _END = 100, 120
_TRANSITION = {"A": "G", "G": "A", "C": "T", "T": "C"}


def _contig(strand: str) -> str:
    body = ["T"] * 300
    body[_START:_END] = list("ACGTACGTACGTACGTACGT")
    if strand == "+":
        body[_END : _END + 3] = list("TGG")  # NGG immediately 3' of the protospacer
    else:
        body[_START - 3 : _START] = list("CCA")  # revcomp of TGG, immediately 5' of it
    return "".join(body)


def _prime_candidates(tmp_path: Path, strand: str, one_based: int) -> list[Any]:
    sequence = _contig(strand)
    fasta = tmp_path / f"{strand}.fa"
    fasta.write_text(">chr1\n" + sequence + "\n")
    base = sequence[one_based - 1]
    menu = design(
        f"chr1:{one_based}:{base}>{_TRANSITION[base]}",
        reference=ReferenceGenome(fasta, build="hg38"),
        run_offtarget=False,
    )
    wanted = f"({strand})"
    return [
        candidate
        for candidate in menu.candidates
        if candidate.chemistry.value == "prime" and str(candidate.pegrna.placement).endswith(wanted)
    ]


@pytest.mark.parametrize(
    ("strand", "edited", "expected_nick"),
    [
        # Three bases 5' of the PAM, counted along the strand that reads the protospacer.
        ("+", 118, _END - 3),
        ("-", 102, _START + 2),
    ],
)
def test_the_nick_is_three_bases_from_the_pam(
    strand: str, edited: int, expected_nick: int, tmp_path: Path
) -> None:
    candidates = _prime_candidates(tmp_path, strand, edited)
    assert candidates, f"no {strand}-strand prime candidate to measure"
    for candidate in candidates:
        pegrna = candidate.pegrna
        assert str(pegrna.placement) == f"chr1:{_START}-{_END}({strand})", pegrna.placement
        assert pegrna.nick_site == expected_nick, (
            f"{strand} strand: nick reported at {pegrna.nick_site}, and SpCas9 cuts three "
            f"bases 5' of the PAM, which for this protospacer is {expected_nick}"
        )


def test_the_two_strands_do_not_share_the_arithmetic(tmp_path: Path) -> None:
    """The check above would pass a single wrong formula applied to both strands.

    `e - 3` and `s + 2` are different numbers for this contig — 117 and 102 — so a
    sign error that made one strand use the other's expression fails, which is the
    error this whole file exists to catch.
    """
    assert _END - 3 != _START + 2
    plus = _prime_candidates(tmp_path, "+", 118)[0].pegrna.nick_site
    minus = _prime_candidates(tmp_path, "-", 102)[0].pegrna.nick_site
    assert plus != minus, (plus, minus)


def test_the_spacer_is_the_patients_allele(tmp_path: Path) -> None:
    """The half that says the geometry is anchored to the right sequence.

    A pegRNA spacer built from the reference would sit at the same coordinates and be a
    different reagent — and would look identical in every field this file checks.
    """
    candidate = _prime_candidates(tmp_path, "+", 118)[0]
    spacer = str(candidate.pegrna.spacer.sequence)
    reference_window = _contig("+")[_START:_END]
    assert spacer != reference_window
    # Exactly one base apart: the one being corrected, at protospacer position 18.
    differing = [i for i, (a, b) in enumerate(zip(spacer, reference_window, strict=True)) if a != b]
    assert differing == [117 - _START], differing
