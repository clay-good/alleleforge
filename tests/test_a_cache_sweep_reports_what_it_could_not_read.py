"""Two of the sweep's own findings could be deleted and the report still read clean.

`verify_stores` is what `aforge cache verify` runs, and its contract is one
:class:`CacheCheck` per artifact. A statement-deletion sweep removed two of the
`checks.append(...)` calls with the whole suite green:

* the **UNREADABLE** branch — an FM-index that fails to load for a reason that is not
  an integrity error at all (a truncated file, a `meta.json` from a different build, a
  permissions problem). The suite covers the neighbouring CORRUPT branch thoroughly, so
  the `except` beside it was taken on trust. Without the append the entry vanishes from
  the report: a sweep run specifically to find a broken index says nothing about it, and
  nothing in the output marks the omission.
* the **bundled** checkpoint line, which exists because packaged bytes are never in the
  cache and "unpinned" would read as a defect in a card that is correct. Without it
  every bundled model is simply absent from a report whose promise is one row per
  artifact.

Both are the same failure: the sweep's job is to say what it found, and a finding it
does not append is indistinguishable from an artifact that is fine.
"""

from __future__ import annotations

import json
from pathlib import Path

from alleleforge.cache_sweep import verify_stores
from alleleforge.model_zoo.registry import default_registry


def _plant_unreadable_index(root: Path) -> str:
    """Put an FM-index entry on disk that `FMIndex.load` cannot make sense of."""
    entry = root / "fm_index" / "not-an-index"
    entry.mkdir(parents=True)
    # Valid JSON, wrong shape: load fails on the contents rather than on the parse,
    # which is the ordinary way a stale entry from an older build presents.
    (entry / "meta.json").write_text(json.dumps({"unexpected": "shape"}))
    return entry.name


def test_an_index_that_cannot_be_read_is_reported(tmp_path: Path) -> None:
    name = _plant_unreadable_index(tmp_path)
    rows = [c for c in verify_stores(tmp_path) if c.artifact == name]
    assert rows, "the unreadable index is missing from the sweep entirely"
    assert rows[0].status == "UNREADABLE", rows[0]
    assert rows[0].detail, "the row must say what went wrong"


def test_the_report_says_which_kind_of_thing_it_was(tmp_path: Path) -> None:
    """A row with no kind cannot be acted on."""
    name = _plant_unreadable_index(tmp_path)
    row = next(c for c in verify_stores(tmp_path) if c.artifact == name)
    assert row.kind == "fm-index"


def test_every_bundled_checkpoint_gets_a_row(tmp_path: Path) -> None:
    """The promise is one row per artifact, and a bundled card is an artifact."""
    zoo = default_registry()
    bundled = [name for name in zoo.names if zoo.get(name).bundled]
    assert bundled, "no bundled card in the zoo; this check would be vacuous"
    reported = {c.artifact for c in verify_stores(tmp_path) if c.kind == "checkpoint"}
    for name in bundled:
        assert name in reported, f"{name} ships in the package and is absent from the sweep"


def test_a_bundled_checkpoint_is_not_reported_as_a_problem(tmp_path: Path) -> None:
    """The reason the row exists: "unpinned" would read as a defect in a correct card."""
    zoo = default_registry()
    bundled = [name for name in zoo.names if zoo.get(name).bundled]
    rows = {c.artifact: c for c in verify_stores(tmp_path) if c.kind == "checkpoint"}
    for name in bundled:
        assert rows[name].status == "bundled", rows[name]
