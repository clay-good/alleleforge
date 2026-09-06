"""A symbol a documented snippet imports must exist.

The docs are already checked in four ways: every CLI command the prose invokes exists,
every flag it names exists, every local link resolves, and every module path it cites
is importable. The fifth claim was unchecked — the `from alleleforge… import X` lines
inside the Python code fences name specific *symbols*, and only their modules were
verified.

So renaming or removing an export left every documented snippet that imports it naming
something that is not there, with the suite green. The snippets are the first thing a
reader copies, and an `ImportError` on line 1 is the worst possible first contact.

The bar is deliberately the imports and not execution. Most blocks are illustrative
fragments that reference names introduced in the surrounding prose (`spacer`, `hg38`,
`menu`), so running them raises `NameError` by design — five of nine README blocks do.
That is a documentation style, not a defect. What a snippet *asserts* is that these
names can be imported from these modules, and that is checkable exactly.
"""

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_DOCS = [_ROOT / "README.md", *sorted((_ROOT / "docs").rglob("*.md"))]
_FENCE = re.compile(r"```python\n(.*?)```", re.S)


def _imports() -> list[tuple[str, str, str]]:
    """Return every `(doc, module, symbol)` a documented Python fence imports."""
    found: list[tuple[str, str, str]] = []
    for doc in _DOCS:
        if not doc.is_file():
            continue
        for block in _FENCE.findall(doc.read_text()):
            try:
                tree = ast.parse(block)
            except SyntaxError:  # pragma: no cover - caught by its own test below
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                    "alleleforge"
                ):
                    assert node.module is not None
                    for alias in node.names:
                        found.append((str(doc.relative_to(_ROOT)), node.module, alias.name))
    return found


def test_there_are_snippets_to_check() -> None:
    """Guard the guard: a regex that matches nothing would pass every case below."""
    found = _imports()
    assert len(found) >= 15, found
    assert any(doc == "README.md" for doc, _, _ in found)


@pytest.mark.parametrize(
    "doc, module, symbol",
    _imports(),
    ids=lambda v: v.replace("/", ".") if isinstance(v, str) else "",
)
def test_the_documented_symbol_exists(doc: str, module: str, symbol: str) -> None:
    imported = importlib.import_module(module)
    assert hasattr(imported, symbol), (
        f"{doc} shows `from {module} import {symbol}`, which does not exist. "
        "A reader copying that snippet gets an ImportError on their first line."
    )


def test_every_python_fence_parses() -> None:
    """A snippet that is not valid Python cannot be copied at all."""
    broken = []
    for doc in _DOCS:
        if not doc.is_file():
            continue
        for block in _FENCE.findall(doc.read_text()):
            try:
                ast.parse(block)
            except SyntaxError as exc:
                broken.append((str(doc.relative_to(_ROOT)), str(exc)))
    assert not broken, broken


def test_the_check_would_notice_a_renamed_export() -> None:
    """Guard the guard, on the mutation that matters: an export that went away."""
    module = importlib.import_module("alleleforge.types")
    assert not hasattr(module, "NoSuchSymbolWasEverExported")
    with pytest.raises(AssertionError, match="ImportError"):
        test_the_documented_symbol_exists(
            "README.md", "alleleforge.types", "NoSuchSymbolWasEverExported"
        )
