"""No user-facing refusal may be a dependency's error report.

`pydantic.ValidationError` subclasses `ValueError`, so every boundary in this
project that catches `ValueError` and prints `str(exc)` prints pydantic's whole
report — an internal model name, a field, a framework's error taxonomy, and a link
to a library the caller never imported::

    error: 1 validation error for PAM
    pattern
      Value error, PAM has non-IUPAC characters: ['X', 'Z'] [type=value_error, ...]
        For further information visit https://errors.pydantic.dev/2.13/v/value_error

One call site had been patched by hand for one model, with a comment saying why. The
class stayed, and `aforge offtarget --pam XYZ` was still printing the report above.

`errors.reason` renders the sentence and nothing else, and every surface that reports
an exception to a person now goes through it: the CLI, the cohort's per-item `error`
column, the designer's per-vertical note, and the job queue's `error` field.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from alleleforge.errors import reason
from alleleforge.types.guide import PAM

_ROOT = Path(__file__).resolve().parents[1]

#: Surfaces that render an exception for a person to read.
#:
#: `web/api/app.py` was missing from the first version of this list, and it is the
#: one place a *client* reads the text: `POST /api/offtarget` with `pam: "XYZ"`
#: answered with pydantic's four-line report inside the JSON `detail`, in the round
#: after the same case was fixed on the command line. A list of surfaces is a scope,
#: and a scope is a place to forget one — so the check also refuses `str(exc)` now,
#: not only `{exc}`.
_REPORTING_SOURCES = [
    _ROOT / "src" / "alleleforge" / "cli" / "main.py",
    _ROOT / "src" / "alleleforge" / "design" / "cohort.py",
    _ROOT / "src" / "alleleforge" / "design" / "designer.py",
    _ROOT / "src" / "alleleforge" / "web" / "api" / "app.py",
    _ROOT / "src" / "alleleforge" / "web" / "api" / "jobs.py",
]

#: An exception rendered straight into a message, which is what leaks the report.
_RAW_INTERPOLATION = re.compile(r"(?<!`)(?:\{exc\}|str\(exc\))(?!`)")


def test_reason_keeps_the_sentence_and_drops_the_machinery() -> None:
    with pytest.raises(ValueError) as excinfo:
        PAM(pattern="XYZ")
    rendered = reason(excinfo.value)
    assert "non-IUPAC" in rendered, rendered
    assert "validation error" not in rendered, rendered
    assert "pydantic" not in rendered, rendered
    assert "input_type" not in rendered, rendered
    assert "Value error," not in rendered, rendered


@pytest.mark.parametrize("exc", [ValueError("plain"), OSError("io"), KeyError("k")], ids=type)
def test_every_other_exception_renders_as_before(exc: Exception) -> None:
    """Safe to apply anywhere `str(exc)` was already printed."""
    assert reason(exc) == str(exc)


def test_a_lookalike_errors_attribute_is_not_interpreted() -> None:
    """Only a real validation error is unwrapped; anything else falls through."""

    class Odd(ValueError):
        def errors(self) -> str:  # not the sequence-of-dicts pydantic returns
            return "not a list"

    assert reason(Odd("odd")) == "odd"


@pytest.mark.parametrize("source", _REPORTING_SOURCES, ids=lambda p: p.name)
def test_no_reporting_surface_interpolates_the_exception_raw(source: Path) -> None:
    lines = source.read_text(encoding="utf-8").splitlines()
    offenders = [
        f"{source.name}:{number}: {line.strip()}"
        for number, line in enumerate(lines, start=1)
        if _RAW_INTERPOLATION.search(line) and not line.lstrip().startswith("#")
    ]
    assert not offenders, (
        "an exception is rendered straight into a user-facing message; a "
        "`ValidationError` there prints pydantic's whole report. Use "
        "`errors.reason(exc)`:\n" + "\n".join(offenders)
    )
