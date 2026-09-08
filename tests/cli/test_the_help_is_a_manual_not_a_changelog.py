"""`--help` is the user's manual, not the project's development log.

Two things had leaked into it. `lift` spent a paragraph explaining that the
liftover "was implemented and tested but reachable only from Python" — true of a
release the reader never used, and no help at all in deciding whether to run the
command. `bench compare` said the digest "had no implementation ... computed,
stored, and read by nothing," which reads, to someone deciding whether to trust
the command, as a description of the command in front of them.

The second check is duller and catches a different accident: two adjacent string
literals concatenated without the space between them, which is invisible in the
source and renders as `assumed.Consumed` to every user who asks for help.
"""

from __future__ import annotations

import re

import click
from typer.main import get_command

from alleleforge.cli.main import app

# Phrases that only make sense to someone who knows what the software used to be.
# Kept narrow deliberately: bare "was" and "did not" are ordinary present-tense
# description ("a number that was edited after signing"), and flagging those
# would train the next reader to add an allowance rather than to rewrite.
_A_PAST_THE_READER_NEVER_SAW = re.compile(
    r"\b(?:used to be|previously|no longer|until (?:now|this release)|"
    r"had no implementation|had not been|had never been|was implemented|"
    r"reachable only from|before this (?:round|change|release))\b",
    re.IGNORECASE,
)

# A sentence terminator glued straight to the next word: ".Consumed".
_GLUED_SENTENCES = re.compile(r"[a-z0-9][.!?][A-Z][a-z]")


def _help_texts() -> dict[str, str]:
    """Every string the CLI will show a user who asks for help, keyed by where."""
    texts: dict[str, str] = {}

    def walk(command: click.Command, name: str) -> None:
        if command.help:
            texts[name] = command.help
        for param in command.params:
            param_help = getattr(param, "help", None)
            if param_help:
                texts[f"{name} --{param.name}"] = param_help
        for sub_name, sub in getattr(command, "commands", {}).items():
            walk(sub, f"{name} {sub_name}")

    walk(get_command(app), "alleleforge")
    return texts


def test_the_help_covers_the_whole_cli() -> None:
    """A vacuity floor: the checks below range over something."""
    texts = _help_texts()
    assert len(texts) > 60, sorted(texts)
    assert "alleleforge lift" in texts
    assert "alleleforge bench compare" in texts


def test_no_help_text_narrates_a_release_the_reader_never_used() -> None:
    offenders = {
        where: _A_PAST_THE_READER_NEVER_SAW.search(text).group(0)  # type: ignore[union-attr]
        for where, text in _help_texts().items()
        if _A_PAST_THE_READER_NEVER_SAW.search(text)
    }
    assert not offenders, (
        "`--help` describes what the software used to be. Say what it does now:\n"
        + "\n".join(f"  {where}: {phrase!r}" for where, phrase in sorted(offenders.items()))
    )


def test_no_help_text_lost_the_space_between_two_literals() -> None:
    offenders = {
        where: text[max(0, match.start() - 30) : match.end() + 30]
        for where, text in _help_texts().items()
        if (match := _GLUED_SENTENCES.search(text))
    }
    assert not offenders, (
        "Two adjacent string literals were concatenated without the space between "
        "them; the reader sees the sentences run together:\n"
        + "\n".join(f"  {where}: …{seen}…" for where, seen in sorted(offenders.items()))
    )
