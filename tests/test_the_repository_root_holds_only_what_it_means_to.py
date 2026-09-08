"""A file named `G` shipped in the repository root for many commits.

    $ cat G
    error: unrecognized variant input: 'chr1:144500000:A'

One line of captured stderr, from a shell redirection typo — `2>G` — during the round that
added the reference-build recommendation, then swept in by a `git add -A`. It has been in
every clone since.

Nothing was going to notice. It broke no test, imported nowhere, and a single-character
filename is the least conspicuous thing in a directory listing next to `CHANGELOG.md` and
`pyproject.toml`. Lint reads Python; the test suite reads what it is pointed at; a diff
review sees one added file among many.

The root is the one directory where a stray file is both most visible to a reader and
least visible to any check, so it gets an explicit inventory. Everything here is named,
with the reason a repository root has it — which also means a genuinely new root file has
to be a decision.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]

#: Every file the repository root is meant to contain, with what it is for. A new entry
#: here should be a considered addition; an unlisted file is a stray until someone says
#: otherwise.
_EXPECTED: dict[str, str] = {
    ".gitignore": "what git ignores",
    ".zenodo.json": "archival metadata for a DOI",
    "CHANGELOG.md": "the release history",
    "CITATION.cff": "how to cite the software",
    "CODE_OF_CONDUCT.md": "community conduct",
    "CONTRIBUTING.md": "how to contribute",
    "Dockerfile": "the container build",
    "LICENSE": "the licence",
    "Makefile": "the developer entry points",
    "README.md": "the front door",
    "RELEASE.md": "the release procedure",
    "SECURITY.md": "how to report a vulnerability",
    "SPEC.md": "the original specification",
    "SPEC_V2.md": "the current specification",
    "conftest.py": "pytest configuration shared by every test package",
    "docker-compose.yml": "the local deployment",
    "mkdocs.yml": "the documentation site build",
    "pyproject.toml": "the package, its dependencies and every tool's configuration",
}


def _tracked_root_files() -> set[str]:
    """Return the files git tracks directly in the repository root."""
    listing = subprocess.run(
        ["git", "ls-files", "--full-name", "."],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    return {name for name in listing if name and "/" not in name}


def test_the_listing_is_not_empty() -> None:
    """A git failure would otherwise make every check below vacuous."""
    assert len(_tracked_root_files()) > 10


def test_no_unexpected_file_is_tracked_in_the_root() -> None:
    stray = sorted(_tracked_root_files() - set(_EXPECTED))
    assert not stray, (
        f"unlisted files tracked in the repository root: {stray}. Add each to _EXPECTED "
        "with what a repository root has it for, or remove it — `G` was one line of "
        "captured stderr and shipped in every clone."
    )


def _untracked_root_files() -> set[str]:
    """Return root files git can see but does not track, ignoring what `.gitignore` covers."""
    listing = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=normal", "--", "."],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    names = (line[3:].strip().strip('"') for line in listing if line.startswith("?? "))
    return {name for name in names if name and "/" not in name}


def test_no_unexpected_file_is_lying_around_in_the_root() -> None:
    """The same check one step earlier, which is the step that matters.

    The tracked version notices a stray only once it has been committed — too late, by
    the definition of the thing it is preventing. And the cause recurs: `G` was captured
    stderr, and `T` was an unquoted `chr…:A>T` on a shell command line, because this
    tool's own variant syntax contains the shell's redirect operator. Both are files
    named after an ALT allele, made by the same accident, two years apart.
    """
    stray = sorted(_untracked_root_files() - set(_EXPECTED))
    assert not stray, (
        f"unlisted files sitting in the repository root: {stray}. A single upper-case "
        "letter is almost certainly an unquoted `>` in a shell command — the ALT allele "
        "of a variant, written to a file. Delete it; `.gitignore` is the wrong answer, "
        "because the next one has a different name."
    )


def test_the_inventory_does_not_outlive_its_files() -> None:
    """An expectation list that names files nobody has stops describing anything."""
    missing = sorted(set(_EXPECTED) - _tracked_root_files())
    assert not missing, f"_EXPECTED names files the root no longer has: {missing}"


@pytest.mark.parametrize("name", sorted(_EXPECTED))
def test_every_expected_file_has_a_reason(name: str) -> None:
    assert len(_EXPECTED[name]) > 8, (name, _EXPECTED[name])
