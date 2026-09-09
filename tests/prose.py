"""Read a document's prose, whatever file the prose happens to live in.

The prose guards took a list of `Path`s and called `read_text()`, which quietly settled
what counts as a document: a file whose whole content is prose. The four example
notebooks carry eleven kilobytes of reader-facing markdown — the coordinate-convention
warning, the population-search explanation, the "what to do next" sections — in
`markdown` cells inside JSON, and no link, command, flag or module-path check had ever
seen a character of it.

The meta-guard written to stop exactly this took its population from `git ls-files
"*.md"`, so it was blind for the same reason one file extension over.
"""

from __future__ import annotations

import json
from pathlib import Path


def prose_text(path: Path) -> str:
    """Return ``path``'s human-readable prose.

    A `.ipynb` yields its markdown cells joined; anything else yields its text. Code
    cells are excluded deliberately: they are executed by `pytest --nbmake` in the gate,
    which is a stronger check than reading them, and `test_examples_teach_the_contract`
    holds them to the uncertainty contract besides.
    """
    if path.suffix == ".ipynb":
        cells = json.loads(path.read_text(encoding="utf-8"))["cells"]
        return "\n\n".join(
            "".join(cell["source"]) for cell in cells if cell["cell_type"] == "markdown"
        )
    return path.read_text(encoding="utf-8")
