"""The window's edges, measured from a genome rather than from a spacer string.

`_editable_positions` is unit-tested against a spacer, and the enumerator is tested at
particular loci. Neither pins the *chain*: a variant resolved to a 0-based coordinate, a
protospacer placed against a PAM, and a 1-based PAM-distal window applied to it. An
off-by-one anywhere along it shifts the window by one position and nothing else changes —
the run still produces candidates, the flags still appear, the report still reads well, and
every reagent is aimed one base off. This repository's own notes record a frame-shifted
scorer window reaching production once.

So the edges are measured here from the outside: build a contig whose protospacer sits at a
known offset with an `AGG` PAM behind it, put the correctable base at each protospacer
position in turn, and require the boundary to fall exactly between 3 and 4 and between 8
and 9 — the documented ABE window, 1-based with PAM-distal as position 1.

Both strands, because the minus strand is where the arithmetic is worst: the spacer is a
reverse complement and every position has to be mapped back through it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from alleleforge.design.designer import design
from alleleforge.enumerate.base_editor import DEFAULT_WINDOW
from alleleforge.genome.reference import ReferenceGenome

_PROTOSPACER_AT = 100
_SPACER_LENGTH = 20
_REVCOMP = {"A": "T", "C": "G", "G": "C", "T": "A"}


def _abe_candidates(
    tmp_path: Path, position: int, *, strand: str, also_at: int | None = None
) -> list[Any]:
    """Design against a contig whose protospacer holds the correctable base at ``position``.

    A `G>A` variant means the patient has an `A` where the reference has a `G`, so
    correcting it is `A -> G`: an adenine base editor's edit, and it must land inside the
    window to be offered.
    """
    protospacer = ["T"] * _SPACER_LENGTH
    protospacer[position - 1] = "G"
    if also_at is not None:
        # A second editable base, to sit just inside or just outside the window. An `A`,
        # not a `G`: the editor edits adenines on the protospacer strand, and the target
        # is a `G` in the *reference* only because the patient's allele there is the `A`
        # being corrected. A bystander is an adenine the reference already has.
        protospacer[also_at - 1] = "A"
    body = ["T"] * 300
    if strand == "+":
        body[_PROTOSPACER_AT : _PROTOSPACER_AT + _SPACER_LENGTH] = protospacer
        body[_PROTOSPACER_AT + _SPACER_LENGTH : _PROTOSPACER_AT + _SPACER_LENGTH + 3] = list("AGG")
        locus = _PROTOSPACER_AT + position  # 1-based
    else:
        # The same protospacer read on the minus strand: write its reverse complement to
        # the plus strand, with `CCT` (revcomp of `AGG`) immediately before it.
        reverse = [_REVCOMP[base] for base in reversed(protospacer)]
        body[_PROTOSPACER_AT : _PROTOSPACER_AT + _SPACER_LENGTH] = reverse
        body[_PROTOSPACER_AT - 3 : _PROTOSPACER_AT] = list("CCT")
        # Protospacer position p on the minus strand is the (L - p)th base from the start
        # of the written window, 0-based; +1 for a 1-based locus.
        locus = _PROTOSPACER_AT + (_SPACER_LENGTH - position) + 1

    fasta = tmp_path / f"{strand}{position}.fa"
    fasta.write_text(">chr1\n" + "".join(body) + "\n")
    reference = ReferenceGenome(fasta, build="hg38")
    ref_base = "".join(body)[locus - 1]
    assert ref_base == ("G" if strand == "+" else "C"), (strand, position, ref_base)
    # The patient's allele, on the plus strand. On the minus strand the correctable base
    # is still `A -> G` *read along the minus strand*, which is `T -> C` written on the
    # plus strand — so the plus-strand variant is `C>T`, not the `C>G` a naive complement
    # of the plus-strand case gives, and that is a transversion no base editor installs.
    alt = "A" if strand == "+" else "T"
    menu = design(
        f"chr1:{locus}:{ref_base}>{alt}",
        reference=reference,
        run_offtarget=False,
    )
    return [c for c in menu.candidates if c.chemistry.value == "base_abe"]


@pytest.mark.parametrize("strand", ["+", "-"])
@pytest.mark.parametrize("position", range(1, 11))
def test_the_window_edges_are_where_the_editor_says(
    position: int, strand: str, tmp_path: Path
) -> None:
    start, end = DEFAULT_WINDOW
    candidates = _abe_candidates(tmp_path, position, strand=strand)
    in_window = start <= position <= end
    wrong = "no candidate for an in-window target" if in_window else "a candidate for one outside"
    assert bool(candidates) == in_window, (
        f"protospacer position {position} on the {strand} strand: {wrong} "
        f"(window is {DEFAULT_WINDOW}, 1-based, PAM-distal = 1)"
    )
    if in_window:
        window = candidates[0].base_edit_window
        assert window.target_positions == (position,), window.target_positions
        assert window.window == DEFAULT_WINDOW


def test_the_sweep_crosses_both_edges(tmp_path: Path) -> None:
    """A sweep that never left the window would pass whatever the arithmetic did."""
    start, end = DEFAULT_WINDOW
    assert 1 < start and end < 10, (
        f"the window {DEFAULT_WINDOW} now reaches the ends of the swept range, so the "
        "boundary cases above no longer sit inside it"
    )


@pytest.mark.parametrize(
    ("bystander", "expected"),
    [(3, ()), (4, (4,)), (6, (6,)), (8, (8,)), (9, ())],
)
def test_the_bystander_edges_are_the_same_edges(
    bystander: int, expected: tuple[int, ...], tmp_path: Path
) -> None:
    """A second editable base is a bystander only inside the window.

    The eligibility check above and the bystander scan are *two* pieces of window
    arithmetic — `window[0] <= ppos <= window[1]` for the target, `_editable_positions`
    for the rest — and only the first is exercised by a spacer holding one editable base.
    Shifting the second by one changes no candidate's existence and no flag; it changes
    the expected number of unintended edits, which is the number a reader acts on.
    """
    target = 5
    if bystander == target:  # pragma: no cover - the parameters avoid it
        pytest.skip("the bystander would be the target")
    candidates = _abe_candidates(tmp_path, target, strand="+", also_at=bystander)
    assert candidates, "the in-window target no longer yields a candidate"
    window = candidates[0].base_edit_window
    assert window.target_positions == (target,)
    assert window.bystander_positions == expected, (
        f"a second editable base at protospacer position {bystander} is reported as "
        f"{window.bystander_positions}, expected {expected} for window {DEFAULT_WINDOW}"
    )
