"""The exit-code vocabulary is written out four times; one copy was checked.

`ExitCode` defines them. `openspec/specs/cli/spec.md` restates them and is pinned to the
enum by `test_the_shipped_specs_describe_the_shipped_cli`. `docs/api/cli.md` restates them
in a table and `README.md` in a sentence, and nothing checked either.

Exit codes are the one part of a CLI that scripts branch on, so a fifth code — or a
renumbering — would leave two documents telling pipeline authors the wrong thing while the
suite stayed green. The guard that exists for one copy is the argument for guarding the
others; it was written for the copy that prompted it.
"""

from __future__ import annotations

import re
from pathlib import Path

from alleleforge.cli.main import ExitCode

_ROOT = Path(__file__).resolve().parents[1]
_CLI_DOC = (_ROOT / "docs" / "api" / "cli.md").read_text(encoding="utf-8")
_README = (_ROOT / "README.md").read_text(encoding="utf-8")


def _codes_in_doc_table() -> set[int]:
    section = _CLI_DOC.split("## Exit codes", 1)[1].split("\n## ", 1)[0]
    return {int(code) for code in re.findall(r"^\|\s*`(\d+)`\s*\|", section, re.M)}


def _codes_in_readme_sentence() -> set[int]:
    match = re.search(r"\*\*Exit codes are distinct and scriptable\*\*:(.+?)\n\n", _README, re.S)
    assert match, "the README no longer states the exit codes where this test looks"
    return {int(code) for code in re.findall(r"`(\d+)`", match.group(1))}


def test_the_cli_reference_table_matches_the_enum() -> None:
    assert _codes_in_doc_table() == {int(code) for code in ExitCode}


def test_the_readme_sentence_matches_the_enum() -> None:
    assert _codes_in_readme_sentence() == {int(code) for code in ExitCode}


def test_the_two_documents_agree_with_each_other() -> None:
    """They are read by different people and drift independently."""
    assert _codes_in_doc_table() == _codes_in_readme_sentence()
