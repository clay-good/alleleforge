"""Asking for a corpus that is not there must list the ones that are.

`load_dataset(name)` and `load_split(task, version)` both refuse a missing file with a
`FileNotFoundError` that *enumerates what the directory actually holds*. That listing is
the whole point of the refusal: these names are not paths a user typed from a file
browser, they are identifiers copied out of documentation, a leaderboard row, or a
previous run's provenance. When one does not resolve, the question is always "then what
is it called now?", and the answer is in the directory the loader just looked in.

Deleting either raise does not stop the call — it drops through to
`json.loads(path.read_text())` on a file that does not exist, so the user gets a bare
`FileNotFoundError` from the standard library naming a path inside the installed package
and nothing else. The remedy (`available_datasets()`, or any of the names it would have
printed) is then undiscoverable from the error.

Both deletions survived `tests/benchmark`.

This matters more here than for an ordinary loader because the benchmark corpus is the
project's honesty surface: a leaderboard row cites a dataset and a split by name, and
`Split.verify` hash-checks both. A name that silently fails to resolve is how a number
gets quoted against the wrong corpus.

Found by deleting each refusal (`scripts/mutate.py --mode raise`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.benchmark.datasets import available_datasets, load_dataset
from alleleforge.benchmark.splits import load_split, splits_root

# -- datasets -----------------------------------------------------------------


def test_a_real_dataset_name_loads() -> None:
    """The premise: at least one name resolves, so the refusals below mean something."""
    names = available_datasets()
    assert names, "no benchmark datasets ship, so nothing here is measuring a lookup"
    assert load_dataset(names[0]) is not None


def test_a_missing_dataset_is_refused_by_name() -> None:
    with pytest.raises(FileNotFoundError, match="no benchmark dataset"):
        load_dataset("not-a-corpus")


def test_the_dataset_refusal_lists_what_is_there() -> None:
    """The listing, not just the refusal: it is what makes the error actionable.

    Without it a user holding a stale identifier has a path inside site-packages and no
    way to learn the current names short of reading this package's source.
    """
    with pytest.raises(FileNotFoundError) as refused:
        load_dataset("not-a-corpus")
    message = str(refused.value)

    assert "'not-a-corpus'" in message, ("the refusal does not echo the name asked for", message)
    for real in available_datasets():
        assert real in message, (
            f"{real!r} ships but the refusal does not offer it, so the listing is "
            "incomplete and a user could rule out a name that would have worked",
            message,
        )


def test_a_dataset_refusal_in_an_empty_directory_still_reads_as_a_listing(
    tmp_path: Path,
) -> None:
    """The degenerate case, which is a different user situation and must not look broken.

    An empty `fixtures_dir` means "you pointed me somewhere with no corpora", not "you
    typed the name wrong". The message has to be readable when the list is empty, which
    an f-string over `[]` is — this pins that it is reached at all rather than crashing
    on the way to it.
    """
    with pytest.raises(FileNotFoundError) as refused:
        load_dataset("anything", fixtures_dir=tmp_path)
    assert "available: []" in str(refused.value), str(refused.value)


# -- splits -------------------------------------------------------------------


def test_a_missing_split_is_refused_by_task_and_version() -> None:
    """A split is keyed by *two* identifiers, and both belong in the message.

    `task.version.json` means a right task at a wrong version is the likeliest mistake —
    a pinned version that has been superseded. A refusal naming only the task would send
    the reader looking for the wrong problem.
    """
    with pytest.raises(FileNotFoundError, match="no split") as refused:
        load_split("not-a-task", version="v9999")
    message = str(refused.value)
    assert "'not-a-task'" in message, message
    assert "v9999" in message, message


def test_the_split_refusal_lists_the_files_that_are_there() -> None:
    """Splits are listed by *filename*, not stem, because the version is in the name.

    `p.name` rather than `p.stem` is deliberate: a listing of bare task names would hide
    which versions exist, which is the half of the identifier a reader is most often
    wrong about.
    """
    with pytest.raises(FileNotFoundError) as refused:
        load_split("not-a-task", version="v9999")
    message = str(refused.value)

    shipped = sorted(p.name for p in splits_root().glob("*.json"))
    assert shipped, "no splits ship, so this listing is not measuring anything"
    for name in shipped:
        assert name in message, (name, message)
    assert ".json" in message, (
        "the listing dropped the extension, so it no longer shows which versions exist",
        message,
    )
