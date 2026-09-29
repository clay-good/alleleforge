"""The CLI reference's exit-code vocabulary matches the implementation.

`ExitCode` defines them. `openspec/specs/cli/spec.md` is pinned to the enum by
`test_the_shipped_specs_describe_the_shipped_cli`; this file covers `docs/api/cli.md`.

Exit codes are the one part of a CLI that scripts branch on, so a fifth code — or a
renumbering — would leave two documents telling pipeline authors the wrong thing while the
suite stayed green. The guard that exists for one copy is the argument for guarding the
reference; it was written for the copy that prompted it.
"""

from __future__ import annotations

import re
from pathlib import Path

from alleleforge.cli.main import ExitCode

_ROOT = Path(__file__).resolve().parents[1]
_CLI_DOC = (_ROOT / "docs" / "api" / "cli.md").read_text(encoding="utf-8")


def _codes_in_doc_table() -> set[int]:
    section = _CLI_DOC.split("## Exit codes", 1)[1].split("\n## ", 1)[0]
    return {int(code) for code in re.findall(r"^\|\s*`(\d+)`\s*\|", section, re.M)}


def test_the_cli_reference_table_matches_the_enum() -> None:
    assert _codes_in_doc_table() == {int(code) for code in ExitCode}
