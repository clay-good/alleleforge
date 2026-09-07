"""Two ways to reuse an expensive scan existed, and only Python could ask for either.

`search()` takes a cross-run `cache` (memoizes a reference-only report,
content-addressed) and a persistent `genome_index` (a memory-mapped per-contig FM-index,
built once and reused). Both are exported, both are parity-tested against the path they
replace, and neither the CLI nor the web API had ever constructed one — so the reference
scan, the expensive deterministic part of every run, was rebuilt from scratch on every
invocation of `aforge offtarget` while a library caller paid once.

`--cache` and `--genome-index` expose them. Neither may change a result, so these check
identity of output as well as reuse of work — and the cache check poisons a stored entry
to prove the read path is live rather than quietly recomputing.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app
from alleleforge.offtarget.cache import OffTargetCache

runner = CliRunner()

_SPACER = "ACGTAACGTTACGTAACGT"


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    """A contig with one perfect match for the spacer at a known offset."""
    rng = random.Random(7)
    seq = "".join(rng.choice("ACGT") for _ in range(4000))
    seq = seq[:100] + _SPACER + "AGG" + seq[122:]
    path = tmp_path / "ref.fa"
    path.write_text(f">chr1\n{seq}\n", encoding="utf-8")
    return path


@pytest.fixture
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the cross-run store at this test's own directory.

    `get_settings()` is a process-wide singleton loaded once, so setting the variable
    is not enough — without dropping the singleton these tests share whichever cache
    dir the first one loaded, which is the developer's real cache.
    """
    import alleleforge.config as config

    root = tmp_path / "cache"
    monkeypatch.setattr(config, "_SETTINGS", None)
    monkeypatch.setenv("ALLELEFORGE_CACHE_DIR", str(root))
    return root


def _run(fasta: Path, *extra: str) -> str:
    result = runner.invoke(
        app,
        ["offtarget", _SPACER, "--reference-fasta", str(fasta), "--json", *extra],
    )
    assert result.exit_code == 0, result.output
    return result.stdout


def test_a_cached_run_reports_what_an_uncached_one_does(fasta: Path, cache_dir: Path) -> None:
    plain = json.loads(_run(fasta))
    cached = json.loads(_run(fasta, "--cache"))
    again = json.loads(_run(fasta, "--cache"))
    assert cached == plain, "the cache flag changed the report"
    assert again == plain, "the second cached run changed the report"


def test_the_second_run_reads_the_store_rather_than_rescanning(
    fasta: Path, cache_dir: Path
) -> None:
    """Poison the stored entry: if the run still rescans, the flag reuses nothing."""
    _run(fasta, "--cache")
    cache = OffTargetCache()
    assert len(cache) == 1, f"one reference scan should have been stored, found {len(cache)}"

    store = cache_dir / "caches" / "offtarget"
    entries = [path for path in store.rglob("*") if path.is_file()]
    assert len(entries) == 1, entries
    poisoned = json.loads(entries[0].read_text(encoding="utf-8"))
    poisoned["sites"] = []
    entries[0].write_text(json.dumps(poisoned), encoding="utf-8")

    served = json.loads(_run(fasta, "--cache"))
    assert served["sites"] == [], (
        "the poisoned entry was not served, so --cache recomputed instead of reusing"
    )


def test_without_the_flag_nothing_is_stored(fasta: Path, cache_dir: Path) -> None:
    """Reuse is opt-in: a plain run must not start writing to a cross-run store."""
    _run(fasta)
    assert len(OffTargetCache()) == 0


def test_the_persistent_index_finds_the_same_sites(fasta: Path, cache_dir: Path) -> None:
    plain = json.loads(_run(fasta))
    indexed = json.loads(_run(fasta, "--genome-index"))
    assert indexed == plain, "the memory-mapped index path changed the report"
