"""The example notebooks' prose is prose, and the prose guards must see it.

Eleven kilobytes of reader-facing markdown live in `markdown` cells inside four `.ipynb`
files — the coordinate-convention warning ("a variant string is read as a 1-based VCF
record … a `Variant` prints its position 0-based"), the population-search explanation, the
next-steps sections. Every prose guard called `read_text()`, so a notebook would have
arrived as JSON, and the meta-guard that checks no document is invisible asked git for
`*.md`. A notebook was therefore unread by construction, twice over.

This pins the unwrapping: the prose is reachable, it is *prose* and not JSON, and the code
cells stay out of it — they are executed by `pytest --nbmake` in the gate, which is a
stronger check than reading them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.prose import prose_text
from tests.test_readme_documents_the_cli import _prose_files

_EXAMPLES = sorted((Path(__file__).resolve().parents[1] / "examples").glob("*.ipynb"))


def test_the_notebooks_are_in_the_prose_corpus() -> None:
    assert _EXAMPLES, "no example notebooks found; this check would be vacuous"
    corpus = {path.resolve() for path in _prose_files()}
    missing = [path.name for path in _EXAMPLES if path.resolve() not in corpus]
    assert not missing, f"notebooks the prose guards do not read: {missing}"


@pytest.mark.parametrize("notebook", _EXAMPLES, ids=lambda p: p.name)
def test_the_prose_comes_back_as_prose(notebook: Path) -> None:
    text = prose_text(notebook)
    assert len(text) > 500, (notebook.name, len(text))
    # Not the raw JSON: `read_text()` would have handed the guards this.
    assert '"cell_type"' not in text, notebook.name
    assert not text.lstrip().startswith("{"), notebook.name


@pytest.mark.parametrize("notebook", _EXAMPLES, ids=lambda p: p.name)
def test_the_code_cells_stay_out(notebook: Path) -> None:
    """Code is executed by the gate; reading it here would double-count and misfire.

    A guard scanning code as prose would read `# aforge design …` in a comment as a
    documented command, and an import as a link.
    """
    cells = json.loads(notebook.read_text(encoding="utf-8"))["cells"]
    code = [c for c in cells if c["cell_type"] == "code"]
    assert code, notebook.name
    prose = prose_text(notebook)
    for cell in code:
        source = "".join(cell["source"]).strip()
        if len(source) > 40:
            assert source not in prose, notebook.name


def test_a_plain_document_is_unchanged(tmp_path: Path) -> None:
    """The floor: unwrapping notebooks must not alter every other file."""
    path = tmp_path / "x.md"
    path.write_text("# Title\n\nBody.\n")
    assert prose_text(path) == "# Title\n\nBody.\n"
