"""Every public module reaches the API reference, or is excluded on the record.

Forty rounds of additions went into modules that had no `:::` directive anywhere —
`design_many`, the cohort entry point with its own README section, among them. The
docs build passes either way: mkdocstrings renders what it is pointed at and says
nothing about what it is not.
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from pathlib import Path

import alleleforge

#: Modules deliberately absent from the API reference, with the reason. Documented
#: elsewhere in prose, or not a library surface at all — but each is a decision.
_NOT_IN_API_REFERENCE: dict[str, str] = {
    "alleleforge.cli.main": "the CLI is documented as commands in api/cli.md, not as functions",
    "alleleforge.web.api.app": "the HTTP surface is documented as endpoints in api/web.md",
    "alleleforge.web.api.models": "request/response schemas are published via OpenAPI",
    "alleleforge.web.api.jobs": "an internal queue behind the HTTP surface, not a library API",
}


def _documented_modules() -> set[str]:
    docs = "\n".join(
        p.read_text() for p in Path(alleleforge.__file__).parents[2].joinpath("docs").rglob("*.md")
    )
    return set(re.findall(r"^:::\s+([\w.]+)", docs, re.M))


def test_every_public_module_is_documented_or_excluded_with_a_reason() -> None:
    documented = _documented_modules()
    assert documented, "no mkdocstrings directives found — the check would be vacuous"

    missing = []
    for module in pkgutil.walk_packages(alleleforge.__path__, "alleleforge."):
        if module.ispkg or module.name.rsplit(".", 1)[1].startswith("_"):
            continue
        if module.name in documented or module.name in _NOT_IN_API_REFERENCE:
            continue
        missing.append(module.name)
    assert not missing, (
        f"modules absent from the API reference: {sorted(missing)}. Add a `::: {missing[0]}` "
        "directive under docs/api/, or list it in _NOT_IN_API_REFERENCE with the reason."
    )


def test_the_exclusion_list_names_only_real_modules() -> None:
    """An exclusion for a module that no longer exists is a stale excuse."""
    for name in _NOT_IN_API_REFERENCE:
        importlib.import_module(name)
