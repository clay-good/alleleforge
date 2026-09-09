"""The code turned the FM-index off by default; the README kept calling it the path.

`FM_INDEX_AUTO_ENGAGES = False` carries the reason in the source: the threshold "turned
the *default* configuration 2.7x slower at exactly the genome scale the tool exists for",
and `scripts/native_speedup.py` "has been printing SLOWER for this pair". The path stays —
it is exact, parity-pinned, and a caller may want a memory-mapped index for *memory* — but
it is reached by asking.

The README went on saying "the genome-scale search **is** the FM-index seed-and-extend
path", listing its speedup as "genome-scale" in a table whose neighbouring row is
scrupulous about being a net cost, and telling a reader to build the crate "for the
genome-scale path" — when the reason to build it is the per-anchor kernels the *linear*
scan calls a million times over 2 Mb.

This is the alarm, derived rather than spelled out: while the engine's auto-engage flag is
off, no document may describe that path as the default. Flip the flag back and the guard
inverts with it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from alleleforge.offtarget.engine import FM_INDEX_AUTO_ENGAGES
from tests.prose import prose_text
from tests.test_readme_documents_the_cli import _prose_files

_ROOT = Path(__file__).resolve().parents[1]

#: Phrases that assert the FM-index is what a default run uses.
_DEFAULT_CLAIMS = (
    "the genome-scale search is the fm-index",
    "the fm-index remains the genome-scale path",
    "build it for the genome-scale path",
)


def test_the_engine_does_not_auto_engage_it() -> None:
    """The premise. If this flips, the claims below become sayable again."""
    assert FM_INDEX_AUTO_ENGAGES is False


def test_no_document_calls_the_opt_in_path_the_default() -> None:
    if FM_INDEX_AUTO_ENGAGES:  # pragma: no cover - the flag is off today
        pytest.skip("the FM-index auto-engages again; these claims are true")
    offenders: list[str] = []
    for path in _prose_files():
        text = prose_text(path).lower()
        for claim in _DEFAULT_CLAIMS:
            if claim in text:
                offenders.append(f"{path.relative_to(_ROOT)}: {claim!r}")
    assert not offenders, (
        "`FM_INDEX_AUTO_ENGAGES` is False — the engine reaches this path only when asked "
        f"— and these documents present it as the default: {offenders}"
    )


def test_the_readme_says_the_path_is_opt_in() -> None:
    """Not saying the wrong thing is half of it; a reader still needs the right one."""
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    row = next(line for line in readme.splitlines() if line.startswith("| `bwt` |"))
    assert "opt-in" in row, row
    assert "use_fm_index" in row or "genome_index" in row, row
    # And the neighbouring row's honesty, applied here: what it costs, not just that it
    # is optional.
    assert re.search(r"net cost|SLOWER", row), row
