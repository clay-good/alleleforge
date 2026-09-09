"""Both on-disk stores promise atomic writes. One of them was not making them.

`alleleforge.cache` states it as a property a caller may rely on:

    **Atomic writes.** Each value is written to a temp file and then renamed into
    place, so a crash or a concurrent writer can never leave a half-written entry a
    later read would trust (the cohort's parallel path relies on this).

Nothing tested it. And the *other* on-disk store — the FM-index cache, holding the
artifact that is three orders of magnitude larger — wrote its four files in place with
`write_bytes` / `write_text`.

Two runs sharing a cache dir and starting together is enough to matter: the second
truncates `bwt.bin` while the first's `meta.json` is already there, and a third process
reading between them fails the length check and is told its cache is corrupt. Fail-closed,
and a corruption report for a race is still a bug.

Both stores publish temp-then-rename now, and this checks the property rather than the
implementation: after a write, no temp file survives; a write is never observed as a
prefix; and the FM-index's completeness marker is published last, so a crash mid-build
leaves a directory the next run rebuilds instead of loading.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from alleleforge.cache import ContentAddressedCache
from alleleforge.genome import index as index_module
from alleleforge.genome.index import FMIndex

_DIGEST = "a" * 64


def test_a_value_cache_leaves_no_temp_file(tmp_path: Path) -> None:
    cache = ContentAddressedCache("ns", root=tmp_path, verify=True)
    cache.put_bytes(_DIGEST, b"payload")
    leftovers = [p.name for p in tmp_path.rglob("*.tmp")]
    assert not leftovers, leftovers
    assert cache.get_bytes(_DIGEST) == b"payload"


def test_an_index_build_leaves_no_temp_file(tmp_path: Path) -> None:
    FMIndex.build("ACGTACGTTTAGGCCATTACGATCGATTACAGG" * 4, cache_dir=tmp_path, prefer_native=False)
    leftovers = [p.name for p in tmp_path.rglob("*.tmp")]
    assert not leftovers, leftovers


def test_the_index_publishes_every_part_by_rename() -> None:
    """The property, read off the writer: no part of a built index is written in place.

    Checked in the source because the race it prevents needs two processes to observe,
    and a test that spawns them to catch a millisecond window is a flake with a moral.
    """
    source = inspect.getsource(FMIndex._build_to_disk)
    assert "_publish(" in source, source
    for direct in (".write_bytes(", ".write_text("):
        assert direct not in source, (
            f"a part of the index is written in place with {direct}: a reader can see a "
            "prefix of it, which is what the sibling store's atomic-write promise exists "
            "to prevent"
        )
    publish = inspect.getsource(index_module._publish)
    assert ".replace(" in publish and ".tmp" in publish, publish


def test_the_completeness_marker_is_published_last(tmp_path: Path) -> None:
    """`build` treats `meta.json` as "this directory is finished"."""
    import re

    source = inspect.getsource(FMIndex._build_to_disk)
    # The publish *calls*, in order — not every mention of a filename, since the comment
    # above them names `meta.json` while explaining why it goes last.
    published = re.findall(r'_publish\(\s*\n?\s*cache / "([a-z.]+)"', source)
    assert set(published) == {"bwt.bin", "occ.json", "sa.json", "meta.json"}, published
    assert published[-1] == "meta.json", published

    # And the marker is what a later run consults, so a directory without it is rebuilt.
    build = inspect.getsource(FMIndex.build)
    assert 'meta.json").exists()' in build, build


@pytest.mark.parametrize("part", ["bwt.bin", "occ.json", "sa.json", "meta.json"])
def test_a_built_index_has_every_part(tmp_path: Path, part: str) -> None:
    """The floor: publishing atomically must still publish."""
    FMIndex.build("ACGTACGTTTAGGCCATTACGATCGATTACAGG" * 4, cache_dir=tmp_path, prefer_native=False)
    cache = next(p.parent for p in tmp_path.rglob("meta.json"))
    assert (cache / part).is_file(), part
