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

The poisoning had to be re-done properly once the store started verifying its bytes. An
edited payload is now *refused*, which is the whole point of the checksum, so it can no
longer stand in for "the read path is live". A poisoned entry whose sidecar is updated to
match still can: the gate exists against a damaged or edited file, not against a writer
who re-checksums what they wrote, and a run that served the re-signed entry is a run that
read the store. Both halves are checked below.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cache import CacheIntegrityError
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


def _the_only_entry(cache_dir: Path) -> Path:
    """Return the single stored payload (not its checksum sidecar)."""
    store = cache_dir / "caches" / "offtarget"
    entries = [
        path for path in store.rglob("*") if path.is_file() and not path.name.endswith(".sum")
    ]
    assert len(entries) == 1, entries
    return entries[0]


def test_the_second_run_reads_the_store_rather_than_rescanning(
    fasta: Path, cache_dir: Path
) -> None:
    """Poison the stored entry, sidecar and all: if the run rescans, the flag reuses nothing."""
    _run(fasta, "--cache")
    cache = OffTargetCache()
    assert len(cache) == 1, f"one reference scan should have been stored, found {len(cache)}"

    entry = _the_only_entry(cache_dir)
    poisoned = json.loads(entry.read_text(encoding="utf-8"))
    poisoned["sites"] = []
    payload = json.dumps(poisoned).encode()
    entry.write_bytes(payload)
    # Re-checksummed, so this is a *stored* wrong answer rather than a damaged one: the
    # integrity gate is not the thing under test here, reuse is.
    entry.with_name(entry.name + ".sum").write_text(hashlib.sha256(payload).hexdigest())

    served = json.loads(_run(fasta, "--cache"))
    assert served["sites"] == [], (
        "the poisoned entry was not served, so --cache recomputed instead of reusing"
    )


def test_an_edited_entry_is_refused_rather_than_served(fasta: Path, cache_dir: Path) -> None:
    """The gate the sidecar exists for, on the store that holds the safety finding.

    Content-addressing says the *inputs* match; it says nothing about whether the bytes
    are still the bytes that were written. Edited to drop its sites, a two-site scan came
    back as a clean guide — the most reassuring output the system can produce, on the
    opt-in flag whose whole promise is that it changes no result.
    """
    honest = json.loads(_run(fasta, "--cache"))
    assert honest["sites"], "the fixture nominates nothing; this check would be vacuous"

    entry = _the_only_entry(cache_dir)
    edited = json.loads(entry.read_text(encoding="utf-8"))
    edited["sites"] = []
    entry.write_text(json.dumps(edited), encoding="utf-8")

    result = runner.invoke(
        app,
        ["offtarget", _SPACER, "--reference-fasta", str(fasta), "--cache", "--json"],
    )
    assert result.exit_code != 0, result.output
    assert isinstance(result.exception, CacheIntegrityError), result.exception


def test_a_missing_checksum_is_refused_too(fasta: Path, cache_dir: Path) -> None:
    """Otherwise `rm *.sum` defeats the gate and the entry is served unverified."""
    _run(fasta, "--cache")
    entry = _the_only_entry(cache_dir)
    entry.with_name(entry.name + ".sum").unlink()

    result = runner.invoke(
        app,
        ["offtarget", _SPACER, "--reference-fasta", str(fasta), "--cache", "--json"],
    )
    assert result.exit_code != 0, result.output
    assert isinstance(result.exception, CacheIntegrityError), result.exception


def test_without_the_flag_nothing_is_stored(fasta: Path, cache_dir: Path) -> None:
    """Reuse is opt-in: a plain run must not start writing to a cross-run store."""
    _run(fasta)
    assert len(OffTargetCache()) == 0


def test_the_persistent_index_finds_the_same_sites(fasta: Path, cache_dir: Path) -> None:
    plain = json.loads(_run(fasta))
    indexed = json.loads(_run(fasta, "--genome-index"))
    assert indexed == plain, "the memory-mapped index path changed the report"
