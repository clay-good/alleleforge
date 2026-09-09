"""`data list` offered "fetch it" for datasets the registry refuses to download.

The registry's second invariant is that no unverifiable artifact is fetched: a download
requires a pinned `sha256`, and `resolve()` raises `ChecksumError` without one. Seven of
the eight shipped descriptors carry no checksum, so for almost everything in the table the
suggested remedy raises:

    ChecksumError: dataset 'gnomad' has no pinned checksum; refusing to download an
    unverifiable artifact

The refusal is right — this is the guarantee working. The table was the part that had not
been told: it printed "supply or fetch it" uniformly, naming an action the tool declines to
perform for the row it was printed on.

The rows now distinguish the two cases, and this test derives the expectation from each
descriptor rather than hard-coding which datasets are pinned, so adding a checksum to
gnomAD flips its row without anyone remembering to update a fixture.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app
from alleleforge.data.registry import DEFAULT_REGISTRY, dataset_status
from alleleforge.errors import ChecksumError


@pytest.fixture
def rows() -> list[dict[str, object]]:
    result = CliRunner().invoke(app, ["data", "list", "--json"])
    assert result.exit_code == 0, result.output + result.stderr
    return json.loads(result.stdout)["datasets"]


def test_the_table_says_which_rows_can_be_fetched(rows: list[dict[str, object]]) -> None:
    """The table must agree with `dataset_status`, not with a copy of its formula.

    This used to re-derive the answer as `bool(sha256 and source_url)` — the exact
    expression `dataset_status` held at the time. `dataset_status`'s own docstring says
    why that is the wrong shape: four surfaces answer this question and "each one that
    derived it separately got a different answer". The test was a fifth. When the
    definition was corrected — a *bundled* row needs no fetch and `resolve` never
    attempts one for it — the surface and the single source moved together and only the
    copy disagreed.
    """
    for row in rows:
        expected = dataset_status(str(row["name"]), DEFAULT_REGISTRY.get(str(row["name"])))
        assert row["fetchable"] == expected["fetchable"], row["name"]


def test_an_unfetchable_row_does_not_offer_a_fetch() -> None:
    result = CliRunner().invoke(app, ["data", "list"])
    assert result.exit_code == 0
    for line in result.stdout.splitlines():
        if "no pinned checksum, so it cannot be fetched" in line:
            assert "or fetch it with consent" not in line


def test_the_offer_matches_what_resolve_actually_does() -> None:
    """The claim is checkable, so check it: an unpinned dataset really does refuse."""
    unpinned = [
        name for name in DEFAULT_REGISTRY.names if DEFAULT_REGISTRY.get(name).sha256 is None
    ]
    assert unpinned, "every dataset is pinned — this check would be vacuous"
    with pytest.raises(ChecksumError, match="no pinned checksum"):
        DEFAULT_REGISTRY.resolve(unpinned[0], consent=True)


def test_the_bundled_matrix_matches_its_pinned_checksum() -> None:
    """The one dataset that ships: its bytes must be the ones the registry pins.

    Checked here because a stale *cache* entry can make `resolve` fail while the shipped
    file is perfect — which is what a local cache on this machine did, and is exactly the
    hash-on-read guarantee working rather than a defect.
    """
    import hashlib
    from pathlib import Path

    import alleleforge.offtarget as offtarget

    descriptor = DEFAULT_REGISTRY.get("doench-2016-cfd")
    bundled = Path(offtarget.__file__).parent / "cfd_matrix.json"
    assert bundled.is_file()
    assert hashlib.sha256(bundled.read_bytes()).hexdigest() == descriptor.sha256
