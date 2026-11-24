"""Read the commit a local checkout is sitting on, to check it against a card's pin.

Three adapters — Lindel, BE-DICT and PRIDICT2 — do not load a checkpoint file. They are
pointed at a *checkout* (``$ALLELEFORGE_LINDEL_REPO`` and friends) and read several files
plus importable Python from it. A card's ``source_snapshot`` pins the revision those
files are supposed to come from; nothing could compare the two until this module, so the
pin was a claim about an upstream commit with no connection to the directory actually on
disk.

Read rather than shelled out to, for two reasons. `git` need not be installed — a user may
have unpacked a tarball or had the directory handed to them — and a subprocess in a
scoring path is a cost paid on every prediction. The plumbing read here is small and
stable: ``HEAD``, a loose ref, or ``packed-refs``.

Everything returns ``None`` rather than raising. "I cannot tell which revision this is" is
a different statement from "this is the wrong revision", and the caller reports them
differently: the first is a gap in what can be checked, the second is a mismatch worth
acting on. Collapsing them into an exception would make an unpacked tarball — a legitimate
way to supply these models — fail where it should merely be unverifiable.
"""

from __future__ import annotations

import re
from pathlib import Path

#: A full git object name. Short names are not accepted anywhere here: this value is
#: compared against a pinned 40-hex revision, and a prefix match would silently accept a
#: different commit.
_SHA = re.compile(r"^[0-9a-f]{40}$")


def _git_dir(checkout: Path) -> Path | None:
    """Return the ``.git`` directory for ``checkout``, following a gitdir pointer.

    In a linked worktree or a submodule, ``.git`` is a *file* holding
    ``gitdir: <path>`` rather than a directory. Both shapes are real, and a reader that
    only understood the directory would report "cannot tell" for any checkout the user
    made with `git worktree`.
    """
    dot_git = checkout / ".git"
    if dot_git.is_dir():
        return dot_git
    if dot_git.is_file():
        try:
            text = dot_git.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            return None
        if not text.startswith("gitdir:"):
            return None
        target = Path(text.split(":", 1)[1].strip())
        resolved = target if target.is_absolute() else (checkout / target)
        return resolved if resolved.is_dir() else None
    return None


def _ref_dirs(git_dir: Path) -> list[Path]:
    """Return the directories a ref may live in, nearest first.

    In a linked worktree, ``HEAD`` is private to the worktree but **refs are shared**:
    they live in the common directory that ``commondir`` points at, not under
    ``worktrees/<name>/``. A reader that looked only in `git_dir` reported "cannot tell"
    for every worktree — including this repository's own, which is how the omission was
    found.
    """
    dirs = [git_dir]
    commondir = git_dir / "commondir"
    if commondir.is_file():
        try:
            target = Path(commondir.read_text(encoding="utf-8", errors="replace").strip())
        except OSError:
            return dirs
        common = target if target.is_absolute() else (git_dir / target)
        if common.is_dir():
            dirs.append(common.resolve())
    return dirs


def _resolve_ref(git_dir: Path, ref: str) -> str | None:
    """Resolve a ref name to a full sha, from a loose file or ``packed-refs``.

    A freshly cloned repository keeps its refs loose; one that has been gc'd or cloned
    with many branches keeps them packed. A reader that only checked loose refs would
    work on a new clone and quietly stop working later, which is the worst version of
    this to debug.
    """
    for base in _ref_dirs(git_dir):
        found = _resolve_ref_in(base, ref)
        if found is not None:
            return found
    return None


def _resolve_ref_in(git_dir: Path, ref: str) -> str | None:
    """Resolve ``ref`` within one git directory."""
    loose = git_dir / ref
    if loose.is_file():
        try:
            candidate = loose.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            return None
        return candidate if _SHA.match(candidate) else None

    packed = git_dir / "packed-refs"
    if not packed.is_file():
        return None
    try:
        lines = packed.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in lines:
        # `# pack-refs with: ...` header, and `^<sha>` peeled-tag continuation lines.
        if not line or line.startswith(("#", "^")):
            continue
        parts = line.split(maxsplit=1)
        if len(parts) == 2 and parts[1].strip() == ref and _SHA.match(parts[0]):
            return parts[0]
    return None


def checkout_revision(checkout: str | Path | None) -> str | None:
    """Return the full commit sha ``checkout`` is on, or ``None`` if it cannot be read.

    Args:
        checkout: A directory that may be a git checkout. ``None``, an empty path, ``.``
            and a path that does not exist all read as "cannot tell". An unset
            ``$ALLELEFORGE_*_REPO`` arrives as an empty path, which pathlib turns into
            ``.``; answering for the current directory there would report the caller's
            own repository as the model's provenance.

    Returns:
        A 40-character lower-case sha, or ``None`` when the directory is not a git
        checkout, its ``HEAD`` is unreadable, or its ref cannot be resolved.
    """
    if checkout is None:
        return None
    # An unset `$ALLELEFORGE_*_REPO` reaches the adapters as `Path("")`, which pathlib
    # normalizes to `Path(".")` on construction — so by the time it arrives here it is
    # indistinguishable from "the current directory". Reading it would report *the user's
    # own repository* as the model's checkout and then warn that their project is on the
    # wrong revision, which is worse than saying nothing. An unconfigured checkout is
    # unknown, and the adapter refuses it in its own terms a moment later.
    if str(checkout) in ("", "."):
        return None
    path = Path(checkout)
    if not path.is_dir():
        return None
    git_dir = _git_dir(path)
    if git_dir is None:
        return None

    head = git_dir / "HEAD"
    if not head.is_file():
        return None
    try:
        text = head.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None

    if _SHA.match(text):
        # Detached HEAD — which is exactly the state a user lands in after checking out
        # the pinned revision, so it is the case most worth getting right.
        return text
    if text.startswith("ref:"):
        return _resolve_ref(git_dir, text.split(":", 1)[1].strip())
    return None
