"""A revision pin on a checkout adapter must be compared with the directory on disk.

Lindel, BE-DICT and PRIDICT2 are not loaded from a checkpoint file: each is pointed at a
checkout (`$ALLELEFORGE_LINDEL_REPO` and friends) and reads several files plus importable
Python from it. R696 gave their cards a `source_snapshot` revision; nothing compared it
with the directory actually in use, so the pin was a claim about an upstream commit with
no connection to what got loaded.

The behaviour is deliberately a **warning, not a refusal**, and the three cases are
distinct:

* on the pinned revision — silent, nothing to say;
* on a different revision — a warning naming both, because a newer checkout is
  legitimate work (comparing against upstream's latest is a real thing to do) and
  refusing would block it. What must not happen is a run quietly using something other
  than the pin while its provenance names the pin;
* revision unreadable — a warning that says so. An unpacked tarball is a supported way
  to supply these models and cannot report a commit; "I cannot tell" is a different
  statement from "this is wrong", and collapsing them would fail a legitimate setup.

The reader parses git's own plumbing rather than shelling out: `git` need not be
installed, and a subprocess per prediction is a cost on a scoring path. That decision is
why most of this file is about file layouts — and why the worktree case is here, which is
the one the first draft got wrong.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from alleleforge.model_zoo.checkout import checkout_revision
from alleleforge.model_zoo.registry import default_registry
from alleleforge.scoring.cas9_outcome import LindelAdapter

_A = "a" * 40
_B = "b" * 40

_CHECKOUT_CARDS = ("be-dict", "lindel", "pridict2")


# -- reading the revision ------------------------------------------------------


def _loose(tmp_path: Path, *, branch: str = "main", sha: str = _A) -> Path:
    """A checkout whose ref is a loose file — a fresh clone."""
    repo = tmp_path / "loose"
    (repo / ".git" / "refs" / "heads").mkdir(parents=True)
    (repo / ".git" / "HEAD").write_text(f"ref: refs/heads/{branch}\n")
    (repo / ".git" / "refs" / "heads" / branch).write_text(f"{sha}\n")
    return repo


def test_a_loose_ref_is_read(tmp_path: Path) -> None:
    assert checkout_revision(_loose(tmp_path)) == _A


def test_a_detached_head_is_read(tmp_path: Path) -> None:
    """The state a user lands in after checking out the pinned revision.

    So it is the case most worth getting right: following the pin's own instructions
    produces a detached HEAD, and a reader that only understood branches would report
    "cannot tell" for exactly the person who did the right thing.
    """
    repo = tmp_path / "detached"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "HEAD").write_text(f"{_B}\n")
    assert checkout_revision(repo) == _B


def test_a_packed_ref_is_read(tmp_path: Path) -> None:
    """A gc'd or many-branched clone keeps refs packed rather than loose.

    Without this the reader would work on a fresh clone and quietly stop working later,
    which is the worst version of this to debug.
    """
    repo = tmp_path / "packed"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (repo / ".git" / "packed-refs").write_text(
        "# pack-refs with: peeled fully-peeled sorted\n"
        f"{_A} refs/heads/other\n"
        f"{_B} refs/heads/main\n"
        f"^{_A}\n"  # a peeled-tag continuation line, which must be skipped
    )
    assert checkout_revision(repo) == _B


def test_a_worktree_resolves_its_ref_through_commondir(tmp_path: Path) -> None:
    """`.git` as a *file*, with refs in the common dir rather than the worktree's.

    This is the case the first draft got wrong, and it was caught by running the reader
    against this repository — which is itself a worktree, so it returned `None` for a
    checkout that git reads fine. In a linked worktree `HEAD` is private but **refs are
    shared**: they live where `commondir` points, not under `worktrees/<name>/`.
    """
    main = tmp_path / "main"
    (main / ".git" / "refs" / "heads").mkdir(parents=True)
    (main / ".git" / "refs" / "heads" / "topic").write_text(f"{_B}\n")
    wt_git = main / ".git" / "worktrees" / "wt"
    wt_git.mkdir(parents=True)
    (wt_git / "HEAD").write_text("ref: refs/heads/topic\n")
    (wt_git / "commondir").write_text("../..\n")

    repo = tmp_path / "wt"
    repo.mkdir()
    (repo / ".git").write_text(f"gitdir: {wt_git}\n")

    assert checkout_revision(repo) == _B


def test_this_repository_reads_as_its_own_head() -> None:
    """An end-to-end check against git itself, not a fixture.

    The fixtures above assert that the parser handles layouts this test file created. A
    real repository is the only thing that asserts the layouts are the ones git actually
    writes.
    """
    import subprocess

    expected = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert checkout_revision(Path(__file__).resolve().parents[2]) == expected


@pytest.mark.parametrize("missing", [True, False], ids=["missing-dir", "no-git-dir"])
def test_an_unreadable_checkout_is_none_not_an_error(tmp_path: Path, missing: bool) -> None:
    """ "Cannot tell" is a return value, not an exception.

    Two shapes: a path that is not there, and a directory with no `.git` at all — an
    unpacked tarball, which is a supported way to supply these models. Raising here
    would turn a legitimate setup into a crash in a scoring path.
    """
    assert checkout_revision(tmp_path / "nonexistent" if missing else tmp_path) is None


@pytest.mark.parametrize(
    "unset", [None, "", ".", Path("")], ids=["none", "empty", "dot", "Path-empty"]
)
def test_an_unconfigured_checkout_does_not_answer_for_the_current_directory(
    unset: object,
) -> None:
    """The defect this test was written to pin, found by writing it.

    `$ALLELEFORGE_LINDEL_REPO` unset reaches the adapters as `Path("")`, and pathlib
    normalizes that to `Path(".")` *on construction* — so by the time the reader sees it,
    it is indistinguishable from "the current directory". Before the guard, running a
    prediction from inside any git repository made this return **the user's own project
    HEAD**, and the comparison then warned that their repository was on the wrong
    revision of Lindel. Reporting someone's working directory as a model's provenance is
    worse than reporting nothing.

    An unconfigured checkout is unknown here; the adapter refuses it in its own terms a
    moment later. A caller who really means the current directory passes an absolute
    path.
    """
    assert checkout_revision(unset) is None  # type: ignore[arg-type]


def test_a_short_sha_in_head_is_not_accepted(tmp_path: Path) -> None:
    """A prefix must not satisfy a full-revision comparison.

    If a 12-character HEAD were returned, it would never equal a pinned 40-hex revision
    and every run would warn — or, worse, a future prefix comparison would accept a
    different commit.
    """
    repo = tmp_path / "short"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "HEAD").write_text("fdcad580ba76\n")
    assert checkout_revision(repo) is None


# -- comparing it with the card ------------------------------------------------


@pytest.mark.parametrize("name", _CHECKOUT_CARDS)
def test_every_checkout_adapter_card_pins_a_revision(name: str) -> None:
    """The premise. These three have no single artifact, so the revision is the only pin."""
    snapshot = default_registry().get(name).source_snapshot
    assert snapshot is not None, f"{name} lost its source_snapshot"
    assert len(snapshot.revision) == 40


def test_a_checkout_on_the_pinned_revision_is_silent(tmp_path: Path) -> None:
    """The case that must not warn, or the warning becomes noise users learn to ignore."""
    pinned = default_registry().get("lindel").source_snapshot.revision
    repo = tmp_path / "lindel"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "HEAD").write_text(f"{pinned}\n")

    adapter = LindelAdapter(repo_dir=repo, consent=True)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert adapter.check_checkout_revision(repo) == pinned


def test_a_checkout_on_another_revision_warns_and_names_both(tmp_path: Path) -> None:
    """Proceeds, but says so — and names both revisions so the reader can act.

    A warning that said only "mismatch" would leave someone to work out which of the two
    commits they are on.
    """
    pinned = default_registry().get("lindel").source_snapshot.revision
    repo = tmp_path / "lindel"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "HEAD").write_text(f"{_B}\n")

    adapter = LindelAdapter(repo_dir=repo, consent=True)
    with pytest.warns(UserWarning, match="is not the pinned revision") as caught:
        observed = adapter.check_checkout_revision(repo)

    assert observed == _B
    message = str(caught[0].message)
    assert _B[:12] in message, message
    assert pinned[:12] in message, message


def test_an_unreadable_checkout_warns_that_it_cannot_be_checked(tmp_path: Path) -> None:
    """Distinct wording from the mismatch case, because it is a different situation.

    One says "you are on the wrong commit"; this one says "nobody can tell what commit
    this is". A test matching only `UserWarning` would pass with either message, so the
    two are asserted apart.
    """
    repo = tmp_path / "tarball"
    repo.mkdir()
    adapter = LindelAdapter(repo_dir=repo, consent=True)

    with pytest.warns(UserWarning, match="cannot read a git revision") as caught:
        assert adapter.check_checkout_revision(repo) is None
    assert "is not the pinned revision" not in str(caught[0].message)


def test_a_card_with_no_snapshot_says_nothing(tmp_path: Path) -> None:
    """Most cards pin no revision, and they must not warn about it.

    Without this, adding the check would have made every unpinned adapter noisy — which
    is how a useful warning gets silenced project-wide.
    """
    from alleleforge.scoring.cas9_outcome import InDelphiAdapter

    assert default_registry().get("indelphi").source_snapshot is None
    adapter = InDelphiAdapter(consent=True)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert adapter.check_checkout_revision(tmp_path) is None
