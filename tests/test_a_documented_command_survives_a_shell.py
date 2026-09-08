"""Six documented command lines could not be pasted into a shell.

The variant syntax this tool is built around contains `>`, which every POSIX shell reads
as output redirection. So

    aforge design chr2:71:A>C --reference-fasta hg38.fa

creates a file called `C` in the user's directory and hands the tool `chr2:71:A`, which
it then refuses as an unrecognized variant. That was the first command in the CLI
reference, the first in the README's quickstart, and the one in the deployment guide —
the flagship example of the flagship command, on three surfaces.

Nothing caught it because the existing guards ask whether an example names *real* flags
and an input form the shell can *resolve*. Both were true. The question nobody asked is
whether the shell delivers the argument at all.

`>` is what makes this tool's own syntax hostile to its own examples, so the check is
mechanical and permanent rather than a one-off correction.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_DOCS = [
    _ROOT / "README.md",
    _ROOT / "CONTRIBUTING.md",
    *sorted((_ROOT / "docs").rglob("*.md")),
]


def _unquoted_redirect(line: str) -> bool:
    """Return True if ``line`` contains a `>` the shell would read as a redirect.

    Tracked by walking the quote state, because that is precisely what the shell does.
    `shlex` is the wrong tool: it is not a shell, keeps `>` inside an ordinary token, and
    reported every one of these lines as fine.
    """
    quote: str | None = None
    for index, char in enumerate(line):
        if quote is None and char in "\"'":
            quote = char
        elif quote is not None and char == quote:
            quote = None
        elif quote is None and char == ">":
            # A deliberate redirect is written with a space before it (`--json > out`)
            # or as a file-descriptor form (`2>&1`). A `>` welded into the middle of a
            # word is a variant string the shell is about to eat.
            before = line[index - 1] if index else " "
            after = line[index + 1] if index + 1 < len(line) else " "
            if not before.isspace() and after not in "&" and not after.isspace():
                return True
    return False


def _command_lines() -> list[tuple[Path, int, str]]:
    found = []
    for path in _DOCS:
        if not path.is_file():
            continue
        for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw.strip()
            if line.startswith(("aforge ", "$ aforge ")):
                found.append((path, number, line))
    return found


def test_the_scan_finds_commands() -> None:
    assert len(_command_lines()) > 10, "no documented commands found; the check is vacuous"


def test_no_documented_command_hands_its_variant_to_the_shell() -> None:
    offenders = [
        f"{path.relative_to(_ROOT)}:{number}: {line}"
        for path, number, line in _command_lines()
        if _unquoted_redirect(line)
    ]
    assert not offenders, (
        "these documented commands contain an unquoted `>`, so a shell redirects to a "
        "file and the tool receives a truncated argument:\n  " + "\n  ".join(offenders)
    )


@pytest.mark.parametrize(
    ("line", "hostile"),
    [
        ("aforge design chr2:71:A>C --reference-fasta hg38.fa", True),
        ("aforge design 'chr2:71:A>C' --reference-fasta hg38.fa", False),
        ('aforge design "chr2:71:A>C"', False),
        ("aforge design x --json > menu.json", False),
        ("aforge design x 2>&1", False),
    ],
)
def test_the_detector_knows_a_redirect_from_a_variant(line: str, hostile: bool) -> None:
    """Guard the guard: it must flag the defect and leave real redirects alone."""
    assert _unquoted_redirect(line) is hostile, line


def test_a_shell_really_does_truncate_the_unquoted_form(tmp_path: Path) -> None:
    """The claim above, executed rather than asserted.

    Cheap, and it is the whole premise: if a shell did not do this, the rule would be
    superstition.
    """
    script = f"cd {tmp_path} && echo aforge design chr2:71:A>C --reference-fasta hg38.fa"
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True)
    # Nothing on stdout: the shell sent `echo`'s own output into the redirect target,
    # which is exactly the point — the `>` never reached the command.
    assert result.stdout == "", result.stdout
    target = tmp_path / "C"
    assert target.exists(), "the shell did not create the redirect target"
    assert target.read_text().strip() == "aforge design chr2:71:A --reference-fasta hg38.fa"


def test_the_refusal_names_the_shell_as_the_cause() -> None:
    """The truncated form is a specific, recognisable shape, so say what happened."""
    result = subprocess.run(
        [sys.executable, "-m", "alleleforge.cli.main", "resolve", "chr2:71:A"],
        capture_output=True,
        text=True,
        cwd=_ROOT,
        env={"PYTHONPATH": str(_ROOT / "src"), "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode != 0
    message = result.stdout + result.stderr
    assert "quote" in message.lower(), message
    assert re.search(r"'chr2:71:A[<>]?", message), message


def test_an_ordinary_typo_is_not_told_a_story_about_redirection(tmp_path: Path) -> None:
    """The hint is offered for one exact shape, or it becomes noise on every typo."""
    result = subprocess.run(
        [sys.executable, "-m", "alleleforge.cli.main", "resolve", "chr2_71_A_C"],
        capture_output=True,
        text=True,
        cwd=_ROOT,
        env={"PYTHONPATH": str(_ROOT / "src"), "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode != 0
    assert "quote" not in (result.stdout + result.stderr).lower(), result.stdout + result.stderr
