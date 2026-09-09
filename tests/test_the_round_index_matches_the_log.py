"""The round index is generated, and must not drift from the log it indexes.

`openspec/changes/README.md` is a megabyte of narrative — four hundred and fifty-odd
rounds, each with its evidence, its measurements and what it ruled out. That shape is
right for writing a round and useless for finding one, and this project's own experience
is that a hand-maintained list of a thing that grows every round goes stale by
construction: four separate guards this month were found reading a population someone
chose once, in passing.

So `ROUNDS.md` is generated from the log and checked here, like the committed figures and
the exported schemas before it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.round_index import INDEX, LOG, render, rounds

_ROOT = Path(__file__).resolve().parents[1]


def _entries() -> list[tuple[int, str, str]]:
    return rounds(LOG.read_text(encoding="utf-8"))


def test_the_committed_index_is_what_the_generator_produces() -> None:
    assert INDEX.exists(), "run python scripts/round_index.py"
    assert INDEX.read_text(encoding="utf-8") == render(_entries()), (
        "the round index is out of date; run python scripts/round_index.py"
    )


def test_the_check_flag_agrees() -> None:
    """The generator's own `--check`, which a contributor runs before committing."""
    result = subprocess.run(
        [sys.executable, "scripts/round_index.py", "--check"], cwd=_ROOT, capture_output=True
    )
    assert result.returncode == 0, result.stderr.decode()


def test_every_round_in_the_log_has_a_row() -> None:
    entries = _entries()
    assert len(entries) > 400, f"parsed {len(entries)} rounds; the log's headings moved"
    text = INDEX.read_text(encoding="utf-8")
    for number, _title, _lesson in entries:
        assert f"| {number} |" in text, number


def test_the_numbers_ascend() -> None:
    """The log's own navigability rule, restated where a reader scans."""
    numbers = [number for number, _title, _lesson in _entries()]
    assert numbers == sorted(numbers), "the index is out of order"
    assert len(set(numbers)) == len(numbers), "a round number appears twice"


def test_most_rounds_carry_a_lesson() -> None:
    """The index is only worth reading if the column it exists for is mostly full.

    A handful of early rounds predate the habit; if that share ever grows, the index has
    stopped being a table of contents and become a list of titles.
    """
    entries = _entries()
    with_lesson = [entry for entry in entries if entry[2]]
    assert len(with_lesson) / len(entries) > 0.9, (
        f"only {len(with_lesson)} of {len(entries)} rounds close with a lesson"
    )


def test_a_lesson_is_quoted_not_paraphrased() -> None:
    """Every rendered lesson must appear verbatim in the round it came from."""
    log = LOG.read_text(encoding="utf-8")
    collapsed = " ".join(log.split())
    for _number, _title, lesson in _entries():
        if not lesson or lesson.endswith("…"):
            continue
        assert lesson in collapsed, lesson
