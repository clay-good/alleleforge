"""A name the prose points at must resolve, not only one a snippet imports.

Four guards read the documentation already: every CLI command it invokes exists,
every flag it names exists, every local link resolves, and every symbol a ```python
fence *imports* is importable. All four read a particular syntax.

`docs/deployment.md` names `alleleforge.web.api.serve()` in a sentence — no import,
no fence — and that path did not exist: `serve` lives in `...api.app` and the
package exported only `create_app`. The sentence is the one telling a reader to
prefer it over running `uvicorn` against the module-level `app`, *because* it
refuses a non-loopback bind without a token. A reader who followed the advice got an
`AttributeError` and fell back to the unguarded line — the exact outcome the
sentence exists to prevent.

So this checks the other syntax: a dotted `alleleforge…` path in backticks, outside
any code fence, resolves to something that exists.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_DOCS = [_ROOT / "README.md", *sorted((_ROOT / "docs").rglob("*.md"))]
_FENCE = re.compile(r"```.*?```", re.S)
#: A dotted path in backticks, optionally called: `alleleforge.web.api.serve()`.
_DOTTED = re.compile(r"`(alleleforge(?:\.[A-Za-z_][A-Za-z0-9_]*)+)(?:\(\))?`")


def _resolves(path: str) -> bool:
    """Return whether `path` names an importable module or an attribute of one."""
    parts = path.split(".")
    for split in range(len(parts), 0, -1):
        try:
            obj: object = importlib.import_module(".".join(parts[:split]))
        except ImportError:
            continue
        for attr in parts[split:]:
            if not hasattr(obj, attr):
                return False
            obj = getattr(obj, attr)
        return True
    return False


def _prose_paths() -> list[tuple[str, str]]:
    """Return every `(doc, dotted path)` the prose names outside a code fence."""
    found: list[tuple[str, str]] = []
    for doc in _DOCS:
        if not doc.is_file():
            continue
        prose = _FENCE.sub("", doc.read_text(encoding="utf-8"))
        for match in _DOTTED.finditer(prose):
            found.append((str(doc.relative_to(_ROOT)), match.group(1)))
    return found


def test_there_are_paths_to_check() -> None:
    paths = _prose_paths()
    assert len(paths) > 10, paths
    assert any(path == "alleleforge.web.api.serve" for _, path in paths), (
        "the path this check was written for is gone from the prose; if the guide was "
        "reworded, point the floor at whatever it names now"
    )


def test_every_dotted_path_the_prose_names_resolves() -> None:
    missing = sorted({f"{doc}: {path}" for doc, path in _prose_paths() if not _resolves(path)})
    assert not missing, (
        "the documentation points a reader at names that do not exist:\n"
        + "\n".join(f"  {entry}" for entry in missing)
    )


@pytest.mark.parametrize("path", ["alleleforge.web.api.serve", "alleleforge.web.api.create_app"])
def test_the_deployment_entry_points_are_where_the_guide_says(path: str) -> None:
    """Named, so the re-export cannot be tidied away without this failing."""
    assert _resolves(path), path


def test_the_check_would_notice_a_name_that_is_gone() -> None:
    """Guard the guard: the resolver must not say yes to everything."""
    assert not _resolves("alleleforge.web.api.no_such_entry_point")
    assert not _resolves("alleleforge.no_such_module.thing")
