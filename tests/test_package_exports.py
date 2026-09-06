"""A package re-exports what it has already declared public.

Two rules, both mechanical, so neither depends on anyone's taste about what "the API"
is:

1. A name in a **submodule's** ``__all__`` is a statement that the name is public;
   the package must re-export it. `routing.__all__` named the two prime budgets the
   README cites by name, and `alleleforge.design` did not export either.
2. A name the **docs** cite as importable must be importable. `docs/api/report.md`
   cross-references `visible_candidates`, which was reachable only from
   `alleleforge.report.builder`.
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from pathlib import Path

import alleleforge

_ROOT = Path(alleleforge.__file__).parents[2]

#: Packages whose contents are documented as endpoints or commands, not as importable
#: names, so a re-export would be meaningless.
_NOT_A_LIBRARY_SURFACE = {"alleleforge.web", "alleleforge.cli"}


def _packages() -> list[str]:
    return [
        m.name
        for m in pkgutil.walk_packages(alleleforge.__path__, "alleleforge.")
        if m.ispkg and m.name not in _NOT_A_LIBRARY_SURFACE
    ]


def test_a_submodule_all_is_re_exported_by_its_package() -> None:
    """`__all__` in a submodule is a declaration; the package has to honor it."""
    gaps: list[str] = []
    packages = _packages()
    assert packages, "no packages discovered — the check would be vacuous"

    for package_name in packages:
        package = importlib.import_module(package_name)
        exported = set(getattr(package, "__all__", ()))
        for sub in pkgutil.iter_modules(package.__path__, f"{package_name}."):
            leaf = sub.name.rsplit(".", 1)[1]
            if leaf.startswith("_"):
                continue
            module = importlib.import_module(sub.name)
            for name in getattr(module, "__all__", ()):
                if not name.startswith("_") and name not in exported:
                    gaps.append(f"{sub.name}.{name} -> {package_name}")
    assert not gaps, f"declared public in a submodule but not re-exported: {sorted(gaps)}"


def test_every_name_the_docs_cite_is_importable_from_its_package() -> None:
    """A cross-reference to `alleleforge.pkg.name` must resolve at that path."""
    prose = "\n".join(p.read_text() for p in (_ROOT / "docs").rglob("*.md"))
    prose += (_ROOT / "README.md").read_text()

    cited = set(re.findall(r"alleleforge\.([a-z_]+)\.([a-z_]+)\.([A-Za-z_][A-Za-z0-9_]*)", prose))
    # A floor before the assertion: "nothing is unresolvable" is satisfied perfectly by
    # finding nothing to resolve, and a doc reformat or a moved corpus does exactly that.
    assert len(cited) > 10, (
        f"only {len(cited)} cross-references were found; the scan is not working"
    )
    unresolvable: list[str] = []
    for package, _module, name in cited:
        full = f"alleleforge.{package}"
        if full in _NOT_A_LIBRARY_SURFACE:
            continue
        try:
            imported = importlib.import_module(full)
        except ModuleNotFoundError:
            continue
        # A dotted path may name a module rather than a package member; both are fine.
        if not hasattr(imported, name) and not _is_module(f"{full}.{_module}", name):
            unresolvable.append(f"alleleforge.{package}.{name}")
    assert not unresolvable, (
        f"docs cite names their package does not export: {sorted(unresolvable)}"
    )


def _is_module(dotted: str, attribute: str) -> bool:
    """Return whether ``dotted`` names a module that has ``attribute``."""
    try:
        return hasattr(importlib.import_module(dotted), attribute)
    except ModuleNotFoundError:
        return False
