"""The readiness assessment's "still library-only" list had rotted in two days.

`specs/readiness-assessment.md` exists so that "context is not lost across sessions",
and its closing section tells a reader which of `design()`'s inputs no command-line
user can reach — the list you consult before promoting the CLI. Every entry on it was
stale: `--region`/`--regions-bed`, `--encode-tracks`/`--chromatin-track` and the
server-side gnomAD and haplotype env vars had all shipped since it was written, so the
document warned people off capabilities the project had.

The same document's *other* honesty claim carries a regression test and is still true.
This is the missing counterpart: the library-only list is now derived from the code —
bind every `run_design(...)` call in the CLI against `design()`'s signature and the
leftovers are exactly what the table must name.
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

from alleleforge.design.designer import design
from alleleforge.variant.resolver import resolve

_ROOT = Path(__file__).resolve().parents[1]
_CLI = _ROOT / "src" / "alleleforge" / "cli" / "main.py"
_DOC = _ROOT / "specs" / "readiness-assessment.md"
_HEADING = "### `design()` parameters no CLI command supplies"


def _supplied_by_the_cli() -> set[str]:
    """Parameters of ``design()`` that some CLI command supplies, positionally or by name.

    Two call sites count, not one. Several of ``design()``'s inputs are read only
    during resolution, and the CLI resolves the variant itself before handing
    ``design()`` the result — so ``resolve_variant(..., effect=...)`` is exactly as
    much "the user reached it from the command line" as passing it to ``design()``
    would be. Counting only the ``design()`` call site called `--vep` unreachable on
    the day it shipped.
    """
    source = _CLI.read_text(encoding="utf-8")
    for imported in (
        "from alleleforge.design.designer import design as run_design",
        "from alleleforge.variant.resolver import resolve as resolve_variant",
    ):
        assert imported in source, (
            f"the CLI no longer contains {imported!r}; this test would silently find "
            "fewer call sites and pass vacuously"
        )
    order = list(inspect.signature(design).parameters)
    resolve_order = list(inspect.signature(resolve).parameters)
    supplied: set[str] = set()
    calls = 0
    for node in ast.walk(ast.parse(source)):
        name = getattr(node.func, "id", None) if isinstance(node, ast.Call) else None
        if name not in ("run_design", "resolve_variant"):
            continue
        calls += 1
        positional = order if name == "run_design" else resolve_order
        supplied |= set(positional[: len(node.args)])
        supplied |= {kw.arg for kw in node.keywords if kw.arg}
    assert calls, "found no run_design(...) or resolve_variant(...) call sites in the CLI"
    return supplied & set(order)


def _named_in_the_table() -> set[str]:
    text = _DOC.read_text(encoding="utf-8")
    _, _, tail = text.partition(_HEADING)
    assert tail, f"{_DOC.name} no longer has the section {_HEADING!r}"
    return set(re.findall(r"^\| `([a-z_0-9]+)` \|", tail, re.M))


def test_the_assessment_names_exactly_the_cli_unreachable_parameters() -> None:
    unreachable = set(inspect.signature(design).parameters) - _supplied_by_the_cli()
    documented = _named_in_the_table()
    assert documented == unreachable, (
        "specs/readiness-assessment.md lists the design() parameters the CLI cannot "
        f"supply. Reached the CLI since it was written: {sorted(documented - unreachable)}. "
        f"Still unreachable but undocumented: {sorted(unreachable - documented)}."
    )
