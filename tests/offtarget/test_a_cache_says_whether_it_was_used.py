"""`--cache` promises reuse, and a cold cache printed the same run as a warm one.

The flag's whole purpose is not recomputing a scan. Its output is byte-identical either
way — deliberately, because `scripts/reproduce.py` requires a cached run and a computed
run to be the same document — so from the outside the flag was unfalsifiable: a key that
stopped matching (a genome re-copied to a new path, a knob the signature covers, a
namespace version bumped under the user) looks exactly like a warm cache, and the only
symptom is a run that is not faster than it was before.

The store counts what it did, and the shells render it under `--verbose` only. Counters
rather than a log line, because the library must not decide how a shell reports; and never
in the artifact, for the byte-identity above.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app
from alleleforge.offtarget.cache import OffTargetCache

SPACER = "GACCATGCAACCTTGAACGT"


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    path = tmp_path / "g.fa"
    path.write_text(">chr1\n" + "T" * 30 + SPACER + "TGG" + "T" * 30 + "\n")
    return path


def test_a_fresh_store_reports_nothing() -> None:
    """An unused store says nothing at all — there is no reuse to describe."""
    store = OffTargetCache(root=Path("/nonexistent-root-for-this-test"))
    assert store.hits == 0 and store.misses == 0
    assert store.usage() is None


def test_the_counts_follow_the_reads(tmp_path: Path) -> None:
    store = OffTargetCache(root=tmp_path)
    assert store.get("sig-a") is None
    assert (store.hits, store.misses) == (0, 1)
    from alleleforge.types.offtarget import OffTargetReport

    store.put("sig-a", OffTargetReport(spacer=SPACER, pam="NGG", sites=(), searched=True))
    assert store.get("sig-a") is not None
    assert (store.hits, store.misses) == (1, 1)
    assert "1 reused" in (store.usage() or "")


def test_the_command_says_which_run_reused_and_which_computed(fasta: Path, tmp_path: Path) -> None:
    """The user-visible half: two identical invocations, two different accounts."""
    cache = tmp_path / "cache"
    runner = CliRunner()
    argv = [
        "--cache-dir",
        str(cache),
        "--verbose",
        "offtarget",
        SPACER,
        "--reference-fasta",
        str(fasta),
        "--cache",
    ]
    cold = runner.invoke(app, argv)
    assert cold.exit_code == 0, cold.output + cold.stderr
    assert "off-target cache: 0 reused, 1 scan computed" in cold.stderr, cold.stderr

    warm = runner.invoke(app, argv)
    assert warm.exit_code == 0, warm.output + warm.stderr
    assert "off-target cache: 1 reused, 0 scans computed" in warm.stderr, warm.stderr
    # The property that makes this line necessary rather than sufficient: the documents
    # are identical, which is why the account has to be somewhere else.
    assert cold.stdout == warm.stdout


def test_a_run_without_the_flag_says_nothing(fasta: Path, tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "--cache-dir",
            str(tmp_path / "cache"),
            "--verbose",
            "offtarget",
            SPACER,
            "--reference-fasta",
            str(fasta),
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    assert "off-target cache" not in result.stderr, result.stderr


def test_it_is_not_in_the_artifact(fasta: Path, tmp_path: Path) -> None:
    """A cached run and a computed run must remain the same document."""
    cache = tmp_path / "cache"
    runner = CliRunner()
    argv = [
        "--cache-dir",
        str(cache),
        "offtarget",
        SPACER,
        "--reference-fasta",
        str(fasta),
        "--cache",
        "--json",
    ]
    cold = runner.invoke(app, argv)
    warm = runner.invoke(app, argv)
    assert cold.exit_code == warm.exit_code == 0
    assert cold.stdout == warm.stdout
    assert "reused" not in cold.stdout
