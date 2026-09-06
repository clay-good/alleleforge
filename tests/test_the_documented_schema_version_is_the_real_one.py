"""The docs named an export schema version the code had left behind.

`docs/api/cli.md` tells a pipeline author what `schema_version` leads every TSV row
with — the field whose entire job is letting a consumer detect that the columns moved.
The code had shipped two bumps past the documented number and nothing noticed, so the
one value a reader is told to branch on was wrong in the place they read it.
"""

from __future__ import annotations

import re
from pathlib import Path

from alleleforge.report.export import EXPORT_SCHEMA_VERSION

_DOC = Path(__file__).resolve().parents[1] / "docs" / "api" / "cli.md"


def test_the_docs_name_the_shipped_schema_version() -> None:
    text = _DOC.read_text(encoding="utf-8")
    stated = re.findall(r"`schema_version`[^.\n]*?is `(\d+)`", text)
    assert stated, "docs/api/cli.md no longer states the schema version"
    for value in stated:
        assert int(value) == EXPORT_SCHEMA_VERSION, (
            f"docs say schema_version {value}, code exports {EXPORT_SCHEMA_VERSION}"
        )
