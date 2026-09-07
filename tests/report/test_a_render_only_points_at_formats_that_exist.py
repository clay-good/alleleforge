"""Both render caps sent readers to "the lossless JSON/CSV export". Two errors, one line.

There is no CSV export. The formats are JSON, TSV, Parquet, HTML and PDF, and a reader
who follows that sentence looking for a `.csv` finds nothing. And "lossless" is true of
exactly one of them: the JSON carries the whole `DesignReport`, while the flat tables
carry one scalar row per candidate — no allele spectrum, no oligo sequences, no
off-target site list. So the sentence pointed a reader chasing a withheld candidate's
*details* at a file that does not exist, and, failing that, at one that cannot answer.

The sentence is now a shared constant, and the check below is the general form: a
renderer may not name a format this tool does not write. That is mechanical, cheap, and
catches the next invented format rather than this one.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from alleleforge.report.builder import EXPORT_FORMAT_NAMES, WITHHELD_CANDIDATES_NOTE

_REPORT = Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "report"

#: Format-shaped words a render might use. Anything matched here must be in
#: `EXPORT_FORMAT_NAMES` — the list is deliberately wider than the truth so an invented
#: format is caught rather than silently unmatched.
_FORMAT_WORD = re.compile(r"\b(JSON|JSONL|CSV|TSV|Parquet|XLSX|HTML|PDF|SVG|BED|VCF|FASTA)\b")

#: Format names a render may say for a reason other than "we write one".
_ALLOWED_ELSEWHERE: dict[str, str] = {
    "SVG": "the charts are inlined SVG; the render says so as a privacy claim, not an export",
    "VCF": "the coordinate convention is explained by contrast with a VCF record",
    "BED": "the coordinate convention is explained by contrast with a BED interval",
}


def _user_facing_strings(path: Path) -> list[str]:
    """Return the string literals in ``path``, minus comments and docstrings.

    A comment may legitimately discuss a format the tool does not write ("Parquet has no
    comment lines"); a string that reaches a page may not.
    """
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


@pytest.mark.parametrize("module", ["html.py", "pdf.py", "builder.py"])
def test_no_render_names_a_format_this_tool_does_not_write(module: str) -> None:
    invented: set[str] = set()
    for text in _user_facing_strings(_REPORT / module):
        for name in _FORMAT_WORD.findall(text):
            if name in EXPORT_FORMAT_NAMES or name in _ALLOWED_ELSEWHERE:
                continue
            invented.add(name)
    assert not invented, (
        f"report/{module} names {sorted(invented)} to a reader, and this tool writes "
        f"{list(EXPORT_FORMAT_NAMES)}. Name a real format, or record the reason in "
        "_ALLOWED_ELSEWHERE."
    )


def test_the_allowances_are_not_hiding_a_real_format() -> None:
    """An allowance must not excuse something that is simply an export."""
    overlap = sorted(set(_ALLOWED_ELSEWHERE) & set(EXPORT_FORMAT_NAMES))
    assert not overlap, f"these are real exports and need no allowance: {overlap}"


def test_the_withheld_note_names_the_lossless_one_and_the_flat_ones_apart() -> None:
    """ "Lossless" is true of the JSON alone; the flat tables cannot carry the details."""
    note = WITHHELD_CANDIDATES_NOTE
    assert "CSV" not in note
    assert "JSON" in note and "lossless" in note
    assert "TSV" in note and "Parquet" in note
    # The claim is scoped to the JSON, not spread across all three.
    assert note.index("lossless") < note.index("TSV"), note
