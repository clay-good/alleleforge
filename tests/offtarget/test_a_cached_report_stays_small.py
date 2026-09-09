"""The integrity check is only free because the thing it hashes is small.

`OffTargetCache` re-hashes every entry it serves. The argument for that is safety — an
edited entry turned two perfect-match off-targets into a clean guide — and the reason it
costs nothing is separate and unstated until now: a stored report holds the *nominated
sites*, not the genome they were found in. Six real entries measured 521 bytes at the
median and 880 at the largest, so re-hashing one is microseconds inside a warm hit that is
itself two orders of magnitude cheaper than the scan it replaces.

That is a property of what gets cached, and it could change: cache the searched sequence,
or every sub-threshold placement, and the hash goes from free to a fraction of the scan.
This is not a timing test — those are unreliable on a shared machine, and this repo's own
notes say so — it is the *premise* of the timing claim, which is checkable exactly.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.cache import OffTargetCache
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM

#: A stored report an order of magnitude past what the measurement found is a different
#: object with a different cost profile, and the docstring's "free" would need re-earning.
_ENTRY_BUDGET_BYTES = 8_192


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    rng = random.Random(31)
    sequence = "".join(rng.choice("ACGT") for _ in range(8_000))
    fasta = tmp_path / "chr1.fa"
    fasta.write_text(f">chr1\n{sequence}\n")
    return ReferenceGenome(fasta, build="hg38")


def test_a_stored_report_is_small(reference: ReferenceGenome, tmp_path: Path) -> None:
    root = tmp_path / "cache"
    cache = OffTargetCache(root=root)
    sequence = "".join(Path(reference.path).read_text().split("\n")[1:])
    for offset in range(0, 200, 40):
        search(sequence[offset : offset + 20], PAM(pattern="NGG"), reference=reference, cache=cache)

    entries = [
        path for path in root.rglob("*") if path.is_file() and not path.name.endswith(".sum")
    ]
    assert entries, "nothing was cached; this check would be vacuous"
    largest = max(path.stat().st_size for path in entries)
    assert largest < _ENTRY_BUDGET_BYTES, (
        f"a cached report grew to {largest} bytes. The per-read checksum is documented as "
        "free because an entry is a few hundred bytes; if a report now carries the "
        "searched sequence or every sub-threshold placement, that argument needs redoing."
    )


def test_the_entry_holds_sites_and_not_the_genome(
    reference: ReferenceGenome, tmp_path: Path
) -> None:
    """The reason it is small, checked rather than assumed."""
    root = tmp_path / "cache"
    cache = OffTargetCache(root=root)
    sequence = "".join(Path(reference.path).read_text().split("\n")[1:])
    search(sequence[100:120], PAM(pattern="NGG"), reference=reference, cache=cache)

    entry = next(
        path for path in root.rglob("*") if path.is_file() and not path.name.endswith(".sum")
    )
    stored = entry.read_text(encoding="utf-8")
    assert "searched_bases" in stored, "the entry no longer records the search extent"
    # 8,000 bases were searched; none of them are in the file.
    assert sequence[500:600] not in stored, "the cached report carries reference sequence"
