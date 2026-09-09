"""The README told a contributor to run an install that cannot succeed.

    pip install -e ".[core,genome,variant,cli,ml,dev]"

`variant` is `hgvs`; `hgvs` requires `psycopg2` unconditionally; and psycopg2 publishes
**Windows wheels only**, so everywhere else pip builds it from source and stops:

    Error: pg_config executable not found.

That is the first command in the README's install section — the one a new contributor runs
before anything else. Nothing caught it, because **no CI job installs `variant`**: every
job uses `genome-light`, and the project's own development virtualenv has neither `hgvs`
nor `psycopg2` in it. The extra is installed nowhere and was documented as the default.

`CONTRIBUTING.md` had already made the argument against a hand-written line — *"`make
install` rather than a hand-written `pip install -e \\".[dev]\\"` … It is the same extras set
CI installs, kept in one place"* — and the README carried one anyway, and it was the one
that did not work. So the README now points at the same target, and the extras table says
what `variant` additionally needs rather than dropping the capability from the record.

This file keeps two things true: an extra named by a documented install line exists, and
no documented line asks for one that cannot install without a system library. The second
is a named list rather than a resolver run: it has to fail offline, and on the commit that
puts the extra back.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]

#: Extras whose dependency chain needs a system library pip cannot supply, with what.
#: A documented install line may not ask for one of these, because the reader runs it.
_NEEDS_A_SYSTEM_LIBRARY: dict[str, str] = {
    "variant": "hgvs requires psycopg2, which publishes Windows wheels only; every other "
    "platform builds it from source and needs PostgreSQL client headers (libpq-dev / "
    "libpq). Coordinates and genomic `g.` need no projector and work on every install.",
}

#: Documents whose fenced `pip install` lines a reader is expected to run.
_DOCUMENTS = ("README.md", "CONTRIBUTING.md", "docs/deployment.md", "docs/examples.md")


def _install_lines() -> list[tuple[str, str]]:
    """Return ``(document, line)`` for every `pip install` the docs show."""
    found: list[tuple[str, str]] = []
    for name in _DOCUMENTS:
        for line in (_ROOT / name).read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("pip install") or stripped.startswith("$ pip install"):
                found.append((name, stripped))
    return found


def _extras_asked_for(line: str) -> set[str]:
    return {e.strip() for group in re.findall(r"\[([^\]]+)\]", line) for e in group.split(",")}


def _declared_extras() -> set[str]:
    config = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return set(config["project"]["optional-dependencies"])


def test_there_are_documented_install_lines() -> None:
    lines = _install_lines()
    assert len(lines) >= 4, lines


def test_every_extra_a_document_names_exists() -> None:
    declared = _declared_extras()
    unknown = sorted(
        {
            f"{doc}: {extra}"
            for doc, line in _install_lines()
            for extra in _extras_asked_for(line) - declared
        }
    )
    assert not unknown, f"documented install lines name extras pyproject does not define: {unknown}"


def test_no_documented_line_asks_for_an_extra_that_cannot_install() -> None:
    offenders = sorted(
        {
            f"{doc}: {extra} — {_NEEDS_A_SYSTEM_LIBRARY[extra]}"
            for doc, line in _install_lines()
            for extra in _extras_asked_for(line) & set(_NEEDS_A_SYSTEM_LIBRARY)
        }
    )
    assert not offenders, (
        "a reader runs these lines and they fail on a machine without the system "
        f"library: {offenders}"
    )


def test_the_readme_points_at_the_makefile_target_for_a_source_install() -> None:
    """The single place CONTRIBUTING says the extras set lives."""
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    makefile = (_ROOT / "Makefile").read_text(encoding="utf-8")
    target = re.search(r'^install:.*\n\t(pip install -e "\.\[[^\]]+\]")', makefile, re.M)
    assert target, "the Makefile no longer has an `install` target with a pip line"
    assert "make install" in readme, "the README no longer points at `make install`"
    assert target.group(1) in readme, (
        f"the README does not show the extras `make install` uses ({target.group(1)}), so "
        "the two can drift and a contributor cannot see what the command does"
    )


@pytest.mark.parametrize("extra", sorted(_NEEDS_A_SYSTEM_LIBRARY))
def test_a_flagged_extra_still_exists_and_is_still_documented(extra: str) -> None:
    """A flag for an extra that is gone hides the next one; and a capability removed from
    the docs entirely is a different mistake from one documented with its cost."""
    assert extra in _declared_extras(), f"{extra} is flagged but no longer declared"
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    assert f"`{extra}`" in readme, f"{extra} is no longer described in the README's table"
