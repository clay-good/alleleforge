"""The file whose job is being current was the stalest thing in the repository.

`specs/readiness-assessment.md` exists "so context is not lost across sessions", and its
header says its verification numbers are "re-measured, not remembered". They were not: it
claimed 2,871 tests and 17 native parity tests long after those were 2,975 and 71. A
previous round re-measured them by hand and concluded the fix was to *derive* the claims
rather than re-type them — then wrote a guard for the reachability table in the same
document and left the numbers beside it unchecked. A promise with no check behind it.

So: the current section may only state numbers this file can derive from the repository,
and the one number nobody can keep true — an absolute suite-wide test count — is
forbidden outright. "The suite passes" is the claim that matters, and it cannot rot.

Only the *current* section is held to this. The dated sections below it are explicitly
kept for the record and are superseded in the text; freezing history is the point of them.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_DOC = _ROOT / "specs" / "readiness-assessment.md"
#: The heading that ends the current section. Everything after it is dated history.
_HISTORY_MARKER = "## UPDATE 2026-06-23"


def _current_section() -> str:
    text = _DOC.read_text(encoding="utf-8")
    end = text.index(_HISTORY_MARKER)
    assert end > 500, "the current section parsed as almost nothing; the marker moved"
    return text[:end]


def _stated_numbers() -> list[int]:
    """Return the bolded numbers the current section commits to."""
    return [int(n.replace(",", "")) for n in re.findall(r"\*\*([\d,]+)%?\*\*", _current_section())]


def test_the_section_still_states_numbers() -> None:
    """Without this the checks below pass over an empty list."""
    assert len(_stated_numbers()) >= 3, _stated_numbers()


def test_the_source_file_count_is_the_real_one() -> None:
    """`mypy --strict clean (N source files)` — N is countable."""
    actual = len(list((_ROOT / "src" / "alleleforge").rglob("*.py")))
    match = re.search(r"\*\*(\d+)\*\* source files", _current_section())
    assert match, "the section no longer states a source-file count"
    assert int(match.group(1)) == actual, (
        f"the assessment says {match.group(1)} source files; there are {actual}"
    )


def test_the_notebook_count_is_the_real_one() -> None:
    actual = len(list((_ROOT / "examples").glob("*.ipynb")))
    match = re.search(r"\*\*(\d+)\*\* example notebooks", _current_section())
    assert match, "the section no longer states a notebook count"
    assert int(match.group(1)) == actual, (
        f"the assessment says {match.group(1)} notebooks; there are {actual}"
    )


def test_the_coverage_gate_is_the_configured_one() -> None:
    """The gate is a real number with a real home, unlike the coverage it achieves."""
    config = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    addopts = " ".join(config["tool"]["pytest"]["ini_options"]["addopts"])
    match = re.search(r"--cov-fail-under=(\d+)", addopts)
    assert match, "pyproject no longer configures a coverage gate"
    stated = re.search(r"\*\*(\d+)%\*\* gate", _current_section())
    assert stated, "the section no longer states the coverage gate"
    assert stated.group(1) == match.group(1), (
        f"the assessment says the gate is {stated.group(1)}%; pyproject sets {match.group(1)}%"
    )


def test_no_absolute_test_count_is_stated() -> None:
    """The number that cannot be kept true, and adds nothing to "the suite passes".

    Written as a prohibition rather than a comparison on purpose: a guard that re-derives
    the count would fail on the commit that adds a test, which is every other commit, and
    a guard that fails constantly gets deleted or `# noqa`'d rather than obeyed.
    """
    offenders = re.findall(r"([\d,]{3,})\s+tests?\b", _current_section())
    assert not offenders, (
        f"the current section states an absolute test count ({offenders}), which is "
        "wrong by the next commit. Say that the suite passes; the count belongs to a "
        "run, not to a document."
    )
