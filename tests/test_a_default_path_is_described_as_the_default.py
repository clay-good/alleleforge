"""The code turned two paths off by default; the README kept calling them the path.

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

The k-mer prefilter's prose had the same shape and a sharper version of it: the README
said it "**auto-engages only when the seed is selective** (`k ≥ 5` …)" when
`SEED_PREFILTER_AUTO_ENGAGES = False` means it never auto-engages at all, and that "the
prefilter stays because it is exact and **free**" when the module comment ends with the
sentence "What is removed is the assumption that it is free."

This is the alarm, derived rather than spelled out and keyed per flag: while an
auto-engage flag is off, no document may describe that path as the default. Flip a flag
back and its half of the guard inverts with it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from alleleforge.offtarget._search import SEED_PREFILTER_AUTO_ENGAGES
from alleleforge.offtarget.engine import FM_INDEX_AUTO_ENGAGES
from tests.prose import prose_text
from tests.test_readme_documents_the_cli import _prose_files

_ROOT = Path(__file__).resolve().parents[1]

#: Phrases that assert an opt-in path is what a default run uses, per flag. Each entry
#: is checked only while its flag is off, so flipping a flag back inverts the guard
#: instead of needing an edit here.
_DEFAULT_CLAIMS: dict[str, tuple[str, ...]] = {
    "FM_INDEX_AUTO_ENGAGES": (
        "the genome-scale search is the fm-index",
        "the fm-index remains the genome-scale path",
        "build it for the genome-scale path",
    ),
    "SEED_PREFILTER_AUTO_ENGAGES": (
        "auto-engages only when the seed is selective",
        "the prefilter stays because it is exact and free",
    ),
}

_FLAGS = {
    "FM_INDEX_AUTO_ENGAGES": FM_INDEX_AUTO_ENGAGES,
    "SEED_PREFILTER_AUTO_ENGAGES": SEED_PREFILTER_AUTO_ENGAGES,
}


@pytest.mark.parametrize("flag", sorted(_FLAGS))
def test_the_engine_does_not_auto_engage_it(flag: str) -> None:
    """The premise. If one flips, that flag's claims become sayable again."""
    assert _FLAGS[flag] is False


@pytest.mark.parametrize("flag", sorted(_DEFAULT_CLAIMS))
def test_no_document_calls_the_opt_in_path_the_default(flag: str) -> None:
    if _FLAGS[flag]:  # pragma: no cover - both flags are off today
        pytest.skip(f"{flag} is on again; those claims are true")
    offenders: list[str] = []
    for path in _prose_files():
        text = prose_text(path).lower()
        for claim in _DEFAULT_CLAIMS[flag]:
            if claim in text:
                offenders.append(f"{path.relative_to(_ROOT)}: {claim!r}")
    assert not offenders, (
        f"`{flag}` is False — the engine reaches that path only when asked — and these "
        f"documents present it as the default: {offenders}"
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
