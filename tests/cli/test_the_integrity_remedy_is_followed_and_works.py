"""The refusal names an entry and two actions; this performs them.

A refusal is judged on whether it fires and on what it says. The sentence it ends with is a
*second* piece of software, executed by a person, and nothing runs it — which is how
`--no-resume`, named by three messages, came to append a second record per item to the
manifest it ran into.

The cache-integrity refusal is the highest-stakes remedy this tool gives, because the state
it describes is one a user cannot diagnose from the outside:

    prime: STORE INTEGRITY — cache entry <digest> failed integrity check (expected …, got …).
    Nothing here is broken: an entry on this disk is not the bytes that were written. Every
    store is content-addressed, so deleting the named entry is safe and the next run
    recomputes it; `aforge cache verify` checks the rest

Three claims, all executable: the digest names a file that exists, deleting it makes the
next run clean, and `aforge cache verify` is a command that reports the same fault. This
test does exactly that, in that order.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app


@pytest.fixture
def genome(tmp_path: Path) -> Path:
    path = tmp_path / "g.fa"
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    path.write_text(">chr2\n" + "".join(seq) + "\n")
    return path


def _design(cache: Path, genome: Path) -> Any:
    return CliRunner().invoke(
        app,
        [
            "--cache-dir",
            str(cache),
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(genome),
            "--cache",
        ],
    )


def _entries(cache: Path) -> list[Path]:
    return [p for p in cache.rglob("*") if p.is_file() and not p.name.endswith(".sum")]


def test_the_remedy_the_integrity_refusal_names_works(genome: Path, tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    warm = _design(cache, genome)
    assert warm.exit_code == ExitCode.OK, warm.stderr
    stored = _entries(cache)
    assert stored, "nothing was cached, so the rest of this proves nothing"

    # Flip the last bytes of one entry: the shape a half-written or edited cache has.
    target = stored[0]
    target.write_bytes(target.read_bytes()[:-3] + b"ZZZ")

    broken = _design(cache, genome)
    assert broken.exit_code == ExitCode.UNAVAILABLE, broken.stderr
    assert "integrity" in broken.stderr

    # 1. The message names a digest, and it is a file on this disk.
    named = re.search(r"cache entry ([0-9a-f]{16,})", broken.stdout + broken.stderr)
    assert named, broken.stdout[:400]
    matches = [p for p in _entries(cache) if p.name.startswith(named.group(1))]
    assert matches == [target], "the digest in the message is not the entry that is wrong"

    # 2. "deleting the named entry is safe and the next run recomputes it".
    for path in cache.rglob(f"{named.group(1)}*"):
        path.unlink()
    healed = _design(cache, genome)
    assert healed.exit_code == ExitCode.OK, healed.stderr

    # 3. "`aforge cache verify` checks the rest" — and reports the same fault when there
    #    is one, which is what makes it a check rather than a reassurance.
    clean = CliRunner().invoke(app, ["--cache-dir", str(cache), "cache", "verify"])
    assert clean.exit_code == ExitCode.OK, clean.stdout

    again = _entries(cache)[0]
    again.write_bytes(again.read_bytes()[:-3] + b"ZZZ")
    dirty = CliRunner().invoke(app, ["--cache-dir", str(cache), "cache", "verify"])
    assert dirty.exit_code == ExitCode.UNAVAILABLE, dirty.stdout
    assert again.name[:16] in dirty.stdout


def test_the_refusal_still_says_the_tool_is_not_broken(genome: Path, tmp_path: Path) -> None:
    """The half a remedy test can lose: an altered store is not a defect in AlleleForge,
    and a message that reads like one sends a user to file a bug instead of deleting a file.
    """
    cache = tmp_path / "cache"
    _design(cache, genome)
    target = _entries(cache)[0]
    target.write_bytes(target.read_bytes()[:-3] + b"ZZZ")
    result = _design(cache, genome)
    assert "Nothing here is broken" in result.stdout + result.stderr
