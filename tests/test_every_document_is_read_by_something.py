"""Three rounds in a row found a guard reading a subset of this repository's prose.

The specification sweep read one of two spec directories. The environment-variable check
had read every surface except the canonical one. The link, module-path, command and
snippet checks read `README.md` + `docs/` and not `CONTRIBUTING.md` — whose broken
Contributor Covenant link they caught only through the README's copy of the same promise.

Each was fixed by editing a list. The list is the defect: it is written once, by someone
looking at the files in front of them, and inherited forever. So this is the check one
level up — **every markdown file this repository tracks is opened by some test, or is
recorded here with the reason it is not.**

It cannot say a document is checked *well*; the guards above it do that. It says a
document is not invisible, which is the failure mode that keeps recurring.

Its own first version asked git for `*.md` — a population taken from a file extension —
so the four example notebooks, eleven kilobytes of reader-facing markdown cells wrapped in
JSON, were invisible to the check written to stop documents being invisible. They are
covered now, through `tests.prose.prose_text`, which unwraps a notebook's markdown cells;
its code cells are executed by the gate, which is stronger than reading them.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.test_documented_env_vars_are_read import _DOCS as _ENV_DOCS
from tests.test_documented_snippets_import_real_names import _DOCS as _SNIPPET_DOCS
from tests.test_readme_documents_the_cli import _prose_files
from tests.test_the_specs_name_real_things import _spec_files

_ROOT = Path(__file__).resolve().parents[1]

#: Documents no guard reads, each with the reason. A reason is required: this is the
#: place a real gap would hide, and "not yet" is not one of these.
_DELIBERATELY_UNREAD: dict[str, str] = {
    "CHANGELOG.md": "has its own guard (`test_changelog_is_readable`), which checks its "
    "structure rather than its prose against the code",
    "openspec/changes/README.md": "the audit log, guarded by `test_round_log_is_navigable`. "
    "It quotes historical mistakes verbatim on purpose, so checking its prose against "
    "today's code would fail by design",
    "openspec/changes/ROUNDS.md": "generated from the audit log and checked byte-for-byte "
    "against its generator by `test_the_round_index_matches_the_log`, which is stricter "
    "than a prose sweep. Its rows quote the log, so it inherits the same reason the log "
    "itself is excluded",
}

#: Directory prefixes whose contents are historical records rather than descriptions of
#: the software as it is.
_ARCHIVED = ("openspec/changes/archive/",)


def _tracked_documents() -> list[str]:
    """Return every tracked document path, from git rather than a glob.

    A glob would sweep up an untracked scratch file and demand a guard for it; the
    question is about the documents this repository publishes.

    `.ipynb` as well as `.md`: this guard's first version asked git for `*.md`, taking
    its population from a file extension — so the four example notebooks, eleven
    kilobytes of reader-facing markdown cells inside JSON, were invisible to the check
    written to stop documents being invisible.
    """
    listed = subprocess.run(
        ["git", "ls-files", "*.md", "*.ipynb"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert len(listed) > 50, f"git listed {len(listed)} documents; this would be vacuous"
    assert any(name.endswith(".ipynb") for name in listed), "no notebooks listed"
    return sorted(listed)


def _read_by_a_guard() -> set[str]:
    """Every document some guard in this suite opens, as a repo-relative path."""
    corpora = [*_prose_files(), *_SNIPPET_DOCS, *_ENV_DOCS, *_spec_files()]
    return {str(path.resolve().relative_to(_ROOT)) for path in corpora}


def test_every_tracked_document_is_read() -> None:
    read = _read_by_a_guard()
    unread = [
        path
        for path in _tracked_documents()
        if path not in read and path not in _DELIBERATELY_UNREAD and not path.startswith(_ARCHIVED)
    ]
    assert not unread, (
        f"{len(unread)} document(s) no test opens: {unread}. Add them to a guard's "
        "corpus, or record them in _DELIBERATELY_UNREAD with the reason."
    )


def test_the_recorded_exceptions_still_exist() -> None:
    """An exemption for a file that is gone hides the next one."""
    tracked = set(_tracked_documents())
    stale = sorted(name for name in _DELIBERATELY_UNREAD if name not in tracked)
    assert not stale, f"_DELIBERATELY_UNREAD names files this repository no longer has: {stale}"


def test_an_exception_is_not_also_read() -> None:
    """A document both excused and covered is a false record, not a no-op."""
    both = sorted(set(_DELIBERATELY_UNREAD) & _read_by_a_guard())
    assert not both, f"recorded as unread and read by a guard: {both}"


def test_the_archive_is_the_only_bulk_exclusion() -> None:
    """The prefix rule must stay narrow enough to be a statement about history."""
    tracked = _tracked_documents()
    archived = [path for path in tracked if path.startswith(_ARCHIVED)]
    assert archived, "nothing matches the archive prefix; the layout moved"
    assert len(archived) < len(tracked), "the archive rule covers everything"
