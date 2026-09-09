"""The only check that catches a same-length index tamper was reachable from Python alone.

Two on-disk stores hold work a run reuses instead of recomputing, and a run trusts both:
the cross-run off-target report cache (`--cache`) and the persistent FM-index cache
(`--genome-index`). Each knows how to detect a corrupted entry. Neither could be *asked*.

* The report cache re-checks a checksum sidecar — but only when a design happens to read
  that entry, so a damaged cache announces itself in the middle of the run that needed it.
* The FM-index gets constant-time structural checks on load, and those are honest about
  their reach: a flipped byte keeps every structural fact intact. `FMIndex.verify()` is
  what catches that, by reconstructing the text and re-hashing it, and
  `test_a_corrupt_index_cache_is_refused` measures what it prevents — a tampered index
  drops a real occurrence *and* reports positions that are not occurrences at all, so a
  scan nominates off-target loci that do not exist. It is `O(n)`, so it cannot run on
  every load, which makes it exactly the kind of thing a *command* is for. There was no
  command. It was a Python method, in a tool whose users are told to use a CLI.

`aforge cache verify` sweeps both stores. `--deep` adds the index reconstruction, and the
run without it says in so many words what it did not check, rather than printing "ok".
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app

runner = CliRunner()

_SPACER = "ACGTAACGTTACGTAACGT"


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    rng = random.Random(7)
    seq = "".join(rng.choice("ACGT") for _ in range(4000))
    seq = seq[:100] + _SPACER + "AGG" + seq[122:]
    path = tmp_path / "ref.fa"
    path.write_text(f">chr1\n{seq}\n", encoding="utf-8")
    return path


@pytest.fixture
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # `get_settings()` is a process-wide singleton loaded once, so setting the variable
    # is not enough — without dropping the singleton these tests share whichever cache
    # dir the first one loaded, which is the developer's real cache.
    import alleleforge.config as config

    root = tmp_path / "cache"
    monkeypatch.setattr(config, "_SETTINGS", None)
    monkeypatch.setenv("ALLELEFORGE_CACHE_DIR", str(root))
    return root


@pytest.fixture
def warm(fasta: Path, cache_dir: Path) -> Path:
    """Fill both stores by running the command that writes them."""
    result = runner.invoke(
        app,
        [
            "offtarget",
            _SPACER,
            "--reference-fasta",
            str(fasta),
            "--cache",
            "--genome-index",
            "--json",
        ],
    )
    assert result.exit_code == ExitCode.OK, result.output
    return cache_dir


def _verify(*args: str) -> tuple[int, dict[str, object]]:
    result = runner.invoke(app, ["cache", "verify", "--json", *args])
    return result.exit_code, json.loads(result.stdout)


def test_a_clean_cache_verifies(warm: Path) -> None:
    """The premise: both stores are populated and both come back ok."""
    code, payload = _verify()
    checks = payload["checks"]
    assert isinstance(checks, list) and checks, payload
    kinds = {check["kind"] for check in checks}
    assert kinds == {"offtarget-report", "fm-index"}, kinds
    assert all(check["status"].startswith("ok") for check in checks), checks
    assert code == ExitCode.OK


def test_an_edited_report_entry_is_named(warm: Path) -> None:
    """The sweep is proactive: today this is found only when a run reads that entry."""
    entry = next(
        path
        for path in (warm / "caches").rglob("*")
        if path.is_file() and not path.name.endswith(".sum")
    )
    doc = json.loads(entry.read_text())
    doc["sites"] = []
    entry.write_text(json.dumps(doc))

    code, payload = _verify()
    corrupt = [c for c in payload["checks"] if c["status"] == "CORRUPT"]  # type: ignore[union-attr]
    assert [c["kind"] for c in corrupt] == ["offtarget-report"], payload
    assert code == ExitCode.UNAVAILABLE


def test_a_same_length_index_tamper_needs_deep_and_says_so(warm: Path) -> None:
    """The whole reason `--deep` exists, and the reason the shallow run must not say ok."""
    bwt = sorted((warm / "fm_index").glob("*/bwt.bin"))[0]
    data = bytearray(bwt.read_bytes())
    for position in range(0, len(data), 11):
        if data[position] in b"ACGT":
            data[position] = ord("A") if data[position] != ord("A") else ord("C")
    bwt.write_bytes(bytes(data))

    shallow_code, shallow = _verify()
    indexes = [c for c in shallow["checks"] if c["kind"] == "fm-index"]  # type: ignore[union-attr]
    assert all(c["status"] == "ok (structure only)" for c in indexes), indexes
    assert shallow_code == ExitCode.OK

    deep_code, deep = _verify("--deep")
    corrupt = [c for c in deep["checks"] if c["status"] == "CORRUPT"]  # type: ignore[union-attr]
    assert [c["kind"] for c in corrupt] == ["fm-index"], deep
    assert deep_code == ExitCode.UNAVAILABLE


def test_the_shallow_run_states_what_it_did_not_check(warm: Path) -> None:
    """ "ok" for a check that did not run is the failure mode this command is about."""
    result = runner.invoke(app, ["cache", "verify"])
    assert result.exit_code == ExitCode.OK, result.output
    assert "--deep" in result.stdout, result.stdout
    assert "structural checks only" in result.stdout, result.stdout


def test_an_empty_cache_is_not_a_silent_pass(cache_dir: Path) -> None:
    """Nothing checked is not the same sentence as everything checked."""
    result = runner.invoke(app, ["cache", "verify"])
    assert result.exit_code == ExitCode.OK, result.output
    assert "nothing cached" in result.stdout, result.stdout
