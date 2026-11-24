"""`scorer_for` is the string door onto the scorers, and its refusal was unpinned.

`scorer_for(name)` exists so a CLI or an API can select a scorer by string — it is what
made MIT and the Cas12a analog reachable from the product at all, rather than only by
importing the class. Both `aforge offtarget --scorer` and `POST /api/offtarget` go
through it, which means the string it validates comes straight from a user.

The refusal is the whole value of a string door. Deleting it leaves
`_SCORERS_BY_NAME.get(key)` returning `None`, which indexes the class table with `None`
and raises `KeyError: None` — a traceback that names neither the bad value nor the valid
ones. A typo (`--scorer cdf`) would then read as a crash in the library rather than as a
misspelled flag, and the CLI's own `ExitCode.USAGE` handler, which catches `ValueError`,
would not catch it at all: the user gets a traceback and exit 1 instead of a usage error.

Found by deleting the refusal (`scripts/mutate.py --mode raise`); it survived
`tests/offtarget`.
"""

from __future__ import annotations

import pytest

from alleleforge.offtarget.scoring import (
    Cas12aCfdScorer,
    CfdScorer,
    MitScorer,
    scorer_for,
)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("cfd", CfdScorer),
        ("mit", MitScorer),
        ("cfd-cas12a", Cas12aCfdScorer),
        ("cfd_cas12a", Cas12aCfdScorer),
        # The door normalizes, so the shell may be shouted at.
        ("CFD", CfdScorer),
        ("  Mit  ", MitScorer),
    ],
)
def test_every_known_name_selects_its_scorer(name: str, expected: type) -> None:
    """The premise: the names the shells advertise all resolve, case and space aside."""
    assert isinstance(scorer_for(name), expected)


@pytest.mark.parametrize("bad", ["cdf", "", "   ", "mit-cas12a", "cfd cas12a", "none"])
def test_an_unknown_scorer_name_is_refused_as_a_value_error(bad: str) -> None:
    """A `ValueError`, specifically, because that is what the CLI turns into USAGE.

    Deleting the guard raises `KeyError: None` instead, which no handler catches: the
    user gets a traceback where they had a typo.
    """
    with pytest.raises(ValueError, match="unknown scorer"):
        scorer_for(bad)


def test_the_refusal_lists_the_names_the_caller_could_have_used() -> None:
    """A refusal that does not name the alternatives makes the user go read the source.

    The listing deliberately drops the underscored alias, so the message offers one
    spelling per scorer rather than two spellings of the same one.
    """
    with pytest.raises(ValueError) as refused:
        scorer_for("cdf")
    message = str(refused.value)

    assert "'cdf'" in message, ("the refusal does not echo what was asked for", message)
    for offered in ("cfd", "mit", "cfd-cas12a"):
        assert offered in message, (offered, message)
    assert "cfd_cas12a" not in message, (
        "the underscored alias is listed as well as the hyphenated one, so the message "
        "offers two spellings of one scorer and reads as four choices",
        message,
    )
