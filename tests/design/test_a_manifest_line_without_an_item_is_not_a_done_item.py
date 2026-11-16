"""A manifest line that records a status but no item is not a completed item.

``_read_done_ids`` asks two things of every line — ``"item_id" in record`` **and**
``record.get("status") == "ok"`` — and every manifest the suite builds is one the runner
wrote, where a line with a status always carries an item id. The two arms therefore
always agreed, and either could be dropped without a test noticing.

The reader's own docstring is about manifests that are *not* pristine: truncated,
hand-edited, corrupt. A line recording a status without an item is exactly that case,
and it is the one this guard exists for. Drop the ``item_id`` arm and the reader raises
a bare ``KeyError`` — where every other damage it finds raises a ``ValueError`` naming
the file, the line number and why skipping it would silently recompute or silently drop
an item.
"""

from __future__ import annotations

import json
from pathlib import Path

from alleleforge.design.cohort import _read_done_ids


def test_a_status_without_an_item_id_is_skipped(tmp_path: Path) -> None:
    manifest = tmp_path / "run.jsonl"
    manifest.write_text(
        json.dumps({"_run": {"alleleforge_version": "0"}})
        + "\n"
        + json.dumps({"status": "ok"})
        + "\n"
        + json.dumps({"item_id": "real", "status": "ok"})
        + "\n"
    )
    assert _read_done_ids(manifest) == {"real"}


def test_an_item_id_without_a_successful_status_is_skipped(tmp_path: Path) -> None:
    """The other arm, so neither is carrying the test on its own."""
    manifest = tmp_path / "run.jsonl"
    manifest.write_text(
        json.dumps({"item_id": "failed", "status": "error"})
        + "\n"
        + json.dumps({"item_id": "real", "status": "ok"})
        + "\n"
    )
    assert _read_done_ids(manifest) == {"real"}
