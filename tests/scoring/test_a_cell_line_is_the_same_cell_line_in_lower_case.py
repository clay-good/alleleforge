"""`--cell-context hek293t` read as out-of-distribution, and reordered the menu.

The check was an exact, case-sensitive membership test:

    in_dist = cell_context is None or cell_context in PRIDICT_TRAINING_CONTEXTS

with `PRIDICT_TRAINING_CONTEXTS = {"HEK293T", "K562"}`. So a user who typed the cell line
in lower case — or pasted it with a stray space — got every candidate flagged `ood`.

That is not a cosmetic flag. `CAVEAT_FLAGS["ood"]` says what it means: *"the efficiency
prediction is out of distribution for this model — it is ranked on its lower interval
bound, and the point estimate should not be trusted"*. So the case of a cell line name
silently changed both an honesty flag and the order of the menu, and the only signal was
a three-letter flag that says nothing about the cell context.

Found by fuzzing every string-typed CLI input. It is the only one of the family that
behaves this way: `--intent CORRECT`, `--chemistry PRIME` and `--vector-scheme
LENTIGUIDE-BSMBI` are all *refused* with the valid values listed, and `--pam ngg` and
`--scorer CFD` are accepted case-insensitively. This one neither refused nor accepted —
it answered a different question and said nothing.

`HEK 293T` is deliberately still out-of-distribution. Internal spacing is a different
string, and guessing which cell line a user meant is worse than flagging it.
"""

from __future__ import annotations

import pytest

from alleleforge.report.builder import CAVEAT_FLAGS
from alleleforge.scoring.prime_efficiency import (
    PRIDICT_TRAINING_CONTEXTS,
    in_training_distribution,
)


@pytest.mark.parametrize("context", ["HEK293T", "hek293t", "HeK293t", "K562", "k562"])
def test_a_training_context_is_recognised_however_it_is_typed(context: str) -> None:
    assert in_training_distribution(context)


@pytest.mark.parametrize("context", [" HEK293T", "K562 ", "  k562  ", "\tHEK293T\n"])
def test_surrounding_whitespace_is_not_a_different_cell_line(context: str) -> None:
    assert in_training_distribution(context)


def test_no_context_asked_for_is_in_distribution() -> None:
    """The caller made no claim, so there is nothing to be outside of."""
    assert in_training_distribution(None)


@pytest.mark.parametrize("context", ["HeLa", "NOT_A_CELL_LINE", "HEK 293T", "HEK293", ""])
def test_a_context_the_model_was_not_trained_on_is_still_flagged(context: str) -> None:
    """The negative case. `HEK 293T` is deliberately here: internal spacing is a
    different string, and guessing which cell line was meant is worse than flagging it."""
    assert not in_training_distribution(context)


def test_the_folded_set_is_derived_from_the_public_one() -> None:
    """A context added to `PRIDICT_TRAINING_CONTEXTS` cannot be left out of the check."""
    for context in PRIDICT_TRAINING_CONTEXTS:
        assert in_training_distribution(context)
        assert in_training_distribution(context.lower())


def test_the_flag_this_sets_is_the_one_that_changes_the_ranking() -> None:
    """Why a case difference was not cosmetic, kept next to the fix that made it so."""
    assert "lower interval bound" in CAVEAT_FLAGS["ood"]


# --- and the consequence, through `design()`, because a flag is not the harm ---


def test_the_case_of_a_cell_line_does_not_change_the_menu(tmp_path: object) -> None:
    """The end-to-end statement: same run, same cell line, two spellings, one menu.

    Asserted on the ranked result rather than on the flag, because the flag is only how
    the defect was visible — the harm was that the efficiencies were discounted to their
    lower bound and the order changed.
    """
    import random
    from pathlib import Path

    from alleleforge.design.designer import design
    from alleleforge.genome.reference import ReferenceGenome

    assert isinstance(tmp_path, Path)
    rng = random.Random(7)
    sequence = "".join(rng.choice("ACGT") for _ in range(4000))
    fasta = tmp_path / "chr1.fa"
    fasta.write_text(f">chr1\n{sequence}\n")
    reference = ReferenceGenome(fasta, build="hg38")
    alt = "A" if sequence[1999] != "A" else "G"
    variant = f"chr1:2000:{sequence[1999]}>{alt}"

    def menu_for(cell_context: str) -> object:
        return design(
            variant,
            reference=reference,
            cell_context=cell_context,
            run_offtarget=False,
            max_candidates_per_chemistry=5,
        )

    upper = menu_for("HEK293T")
    lower = menu_for("hek293t")
    assert upper.candidates, "no candidate to compare"  # type: ignore[attr-defined]
    assert [c.model_dump_json() for c in upper.candidates] == [  # type: ignore[attr-defined]
        c.model_dump_json()
        for c in lower.candidates  # type: ignore[attr-defined]
    ]

    # And the negative case: a context the model really was not trained on still differs.
    hela = menu_for("HeLa")
    assert [c.model_dump_json() for c in hela.candidates] != [  # type: ignore[attr-defined]
        c.model_dump_json()
        for c in upper.candidates  # type: ignore[attr-defined]
    ]
    assert any("ood" in c.flags for c in hela.candidates)  # type: ignore[attr-defined]
    assert not any("ood" in c.flags for c in upper.candidates)  # type: ignore[attr-defined]
