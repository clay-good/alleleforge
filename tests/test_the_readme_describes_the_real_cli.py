"""The README's claims about the CLI must match the CLI.

The README is 1,400 lines of specific, checkable assertions -- flags, commands, and
statements about behavior -- and until now nothing checked any of them. Two were wrong:
a coordinate-convention row that mislabelled the reports as 1-based (fixed in its own
round), and the claim that `--cell-context` "raises the out-of-distribution flag on every
efficiency prediction", which is true of the prime vertical and of nothing else. That
last one had been corrected in the CLI help and in both web request models in the same
round, and missed here, which is the argument for a check rather than more care.

Two of these are mechanical and cheap: the commands and the flags. The third pins the
one claim that has already gone stale twice.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

README = Path(__file__).resolve().parents[1] / "README.md"

#: Every command group the CLI exposes, so a flag mentioned anywhere is looked for
#: everywhere before being called missing.
COMMANDS = ("", "resolve", "design", "batch", "offtarget", "verify", "lift", "data", "bench")

#: `--flag`-shaped strings in the README that belong to other tools or are anchor links.
#: Each is listed with its owner, so this cannot become a bucket for a real stale flag.
_NOT_OURS: dict[str, str] = {
    "--build": "docker compose up --build",
    "--check": "ruff format --check",
    "--nbmake": "pytest --nbmake",
    "--no-cov": "pytest --no-cov",
    "--port": "uvicorn --port",
    "--release": "maturin develop --release",
    "--strict": "mypy --strict",
    "--api-phase-13-shipping-now": "a markdown anchor link",
    "--oligo-output-phase-11-shipping-now": "a markdown anchor link",
    "--responsible-use": "a markdown anchor link",
}


def _help(*args: str) -> str:
    env = dict(os.environ, COLUMNS="400")
    return subprocess.run(
        ["aforge", *args, "--help"], capture_output=True, text=True, env=env, check=False
    ).stdout


@pytest.fixture(scope="module")
def cli_flags() -> set[str]:
    flags: set[str] = set()
    for command in COMMANDS:
        flags |= set(re.findall(r"--[a-z0-9][a-z0-9-]*", _help(*([command] if command else []))))
    for sub in ("list", "show"):
        flags |= set(re.findall(r"--[a-z0-9][a-z0-9-]*", _help("data", sub)))
    return flags


def _invoked_commands(text: str) -> set[str]:
    """Return the commands the README actually *invokes*, from code contexts only.

    Prose can put any word after "AlleleForge" or "aforge", so scanning the whole file
    finds English, not commands. Fenced blocks and inline code spans are where a real
    invocation lives.
    """
    # Shell-ish fences only. A ```mermaid block is a diagram, and its node labels are
    # placeholders -- `CMD["aforge subcommand"]` is not a command anyone can run.
    fenced = re.findall(r"```(?:bash|sh|console|shell|text)?\n(.*?)```", text, re.S)
    inline = re.findall(r"`([^`\n]+)`", text)
    found: set[str] = set()
    for chunk in [*fenced, *inline]:
        found |= {m.group(1) for m in re.finditer(r"\baforge ([a-z][a-z0-9-]*)", chunk)}
    return found


def test_every_command_the_readme_invokes_exists() -> None:
    """A renamed or removed command must not keep being documented.

    Read from code contexts only. The first version of this scanned the whole file and
    filtered the results against the real command list -- which made it report only
    names that were already real, so it was empty by construction and passed against a
    README that invoked `aforge validate`.
    """
    invoked = _invoked_commands(README.read_text())
    assert len(invoked) >= 5, f"parsed too few commands to be checking anything: {invoked}"
    real = {c for c in COMMANDS if c}
    missing = sorted(invoked - real)
    assert not missing, f"the README invokes commands the CLI does not have: {missing}"


def test_every_flag_the_readme_names_exists(cli_flags: set[str]) -> None:
    assert len(cli_flags) > 30, "the CLI help did not parse; this check would be vacuous"
    mentioned = set(re.findall(r"--[a-z0-9][a-z0-9-]*", README.read_text()))
    missing = sorted(mentioned - cli_flags - set(_NOT_OURS))
    assert not missing, (
        f"flags the README documents that no command has: {missing}. Rename them, or "
        "record them in _NOT_OURS with the tool they belong to."
    )


def test_the_foreign_flag_allowances_are_still_needed() -> None:
    """Guard the guard: an allowance must not outlive the line that needed it."""
    text = README.read_text()
    stale = sorted(f for f in _NOT_OURS if f not in text)
    assert not stale, f"_NOT_OURS lists flags the README no longer mentions: {stale}"


def test_the_readme_does_not_overclaim_the_cell_context() -> None:
    """`--cell-context` is consumed by the prime vertical and by no other.

    SpCas9 nuclease and base editing take no cell context, and their predictions report
    `in_distribution=True` from a check on the *guide* context -- so "every efficiency
    prediction" is the one phrasing that turns a truthful flag into a false claim.
    """
    # Matched over a window of the flowed text, not per line: the sentence this checks
    # wraps across three lines, and the line-based version of it silently matched
    # nothing -- a checker that finds nothing is worse than no checker at all.
    text = " ".join(README.read_text().split())
    assert "out-of-distribution flag on every efficiency prediction" not in text
    marker = "`--cell-context <line>` is what raises the"
    assert marker in text, "the README no longer explains --cell-context; this check is vacuous"
    window = text[text.index(marker) : text.index(marker) + 400]
    assert "out-of-distribution" in window, window
    assert "prime" in window, window
