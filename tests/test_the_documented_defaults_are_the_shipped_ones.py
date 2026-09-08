"""The scientific defaults are restated across six documents and pinned by none.

`search()`'s signature is the authority for the off-target budgets and reporting
thresholds; `PBS_RANGE` and `RTT_RANGE` are the authority for pegRNA geometry. Between
the README's feature table, its parameter table, its architecture diagram, the prime API
page and the population concepts page, those numbers appear more than a dozen times.

They agree today, by hand. A reader takes them as the tool's operating envelope — "report
CFD >= 0.20 or MIT >= 0.10", "PBS 8-17 nt" — and would have no way to know a default had
moved. The exit codes got a guard in the previous round for the same reason, and these are
the numbers a scientific claim rests on rather than a shell script.

Written as "every documented occurrence must match", not "the docs mention it somewhere":
a stale second copy is the failure mode, so finding one occurrence proves nothing.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PBS_RANGE, RTT_RANGE

_ROOT = Path(__file__).resolve().parents[1]
_DOCS = [_ROOT / "README.md", *sorted((_ROOT / "docs").rglob("*.md"))]
_DEFAULTS = {name: p.default for name, p in inspect.signature(search).parameters.items()}


def _occurrences(pattern: str) -> list[tuple[Path, str]]:
    found = []
    for path in _DOCS:
        for match in re.findall(pattern, path.read_text(encoding="utf-8")):
            found.append((path, match))
    return found


def test_every_documented_cfd_threshold_is_the_default() -> None:
    hits = _occurrences(r"CFD [>≥]=? ?([0-9.]+)")
    assert hits, "no documented CFD threshold — this check would be vacuous"
    for path, value in hits:
        assert float(value) == _DEFAULTS["cfd_threshold"], f"{path.name} says CFD >= {value}"


def test_every_documented_mit_threshold_is_the_default() -> None:
    hits = _occurrences(r"MIT [>≥]=? ?([0-9.]+)")
    assert hits, "no documented MIT threshold"
    for path, value in hits:
        assert float(value) == _DEFAULTS["mit_threshold"], f"{path.name} says MIT >= {value}"


def test_every_documented_mismatch_budget_is_the_default() -> None:
    hits = _occurrences(r"[≤<]=? ?([0-9]+) ?mismatch")
    assert hits, "no documented mismatch budget"
    for path, value in hits:
        assert int(value) == _DEFAULTS["mismatches"], f"{path.name} says <= {value} mismatches"


def test_every_documented_pbs_and_rtt_range_is_the_real_one() -> None:
    for label, expected in (("PBS", PBS_RANGE), ("RTT", RTT_RANGE)):
        hits = _occurrences(rf"{label} ([0-9]+)[-–]([0-9]+)")
        assert hits, f"no documented {label} range"
        for path, (low, high) in hits:
            assert (int(low), int(high)) == expected, (
                f"{path.name} says {label} {low}-{high}, the code ships {expected}"
            )


#: `search()`'s numeric defaults, and the prose pattern each is written as. A default
#: with no pattern is either a number no document quotes or one nobody is checking, and
#: the test below refuses to let that difference go unrecorded.
_DOCUMENTED_AS: dict[str, str] = {
    "cfd_threshold": r"CFD [>≥]=? ?([0-9.]+)",
    "mit_threshold": r"MIT [>≥]=? ?([0-9.]+)",
    "mismatches": r"[≤<]=? ?([0-9]+) ?mismatch",
    # Written as "≤ 1 DNA + ≤ 1 RNA bulge", so only the second carries the word.
    "dna_bulges": r"[≤<]=? ?([0-9]+) ?DNA\b",
    "rna_bulges": r"[≤<]=? ?([0-9]+) ?RNA bulge",
    "maf": r"MAF [>≥]=? ?([0-9.]+)",
}


def _numeric_defaults() -> dict[str, float]:
    """Return `search()`'s numeric defaults — the operating envelope a reader is quoted."""
    found = {
        name: value
        for name, value in _DEFAULTS.items()
        if isinstance(value, int | float) and not isinstance(value, bool)
    }
    assert len(found) > 4, f"introspection returned {found}; the check would be vacuous"
    return found


def test_every_numeric_default_has_a_documented_pattern() -> None:
    """The half that was missing: three of six defaults had no check at all.

    `cfd_threshold`, `mit_threshold` and `mismatches` were pinned; the bulge budgets and
    the MAF floor were not, and they are restated across five documents in exactly the
    same way — "≤ 1 DNA + ≤ 1 RNA bulge", "MAF ≥ 0.001". Enumerating the defaults rather
    than listing the checked ones is what makes a *new* default impossible to forget:
    the previous shape could only ever cover what someone remembered to add.
    """
    unchecked = sorted(set(_numeric_defaults()) - set(_DOCUMENTED_AS))
    assert not unchecked, (
        f"`search()` ships {unchecked} and no document is checked to quote them "
        "correctly. Add the prose pattern, or — if no document quotes it — say so here."
    )


def test_no_pattern_outlives_its_default() -> None:
    stale = sorted(set(_DOCUMENTED_AS) - set(_numeric_defaults()))
    assert not stale, f"_DOCUMENTED_AS names parameters `search()` no longer has: {stale}"


@pytest.mark.parametrize("name", sorted(_DOCUMENTED_AS))
def test_every_documented_occurrence_matches_the_default(name: str) -> None:
    """Every occurrence, not one: a stale second copy is the failure mode."""
    hits = _occurrences(_DOCUMENTED_AS[name])
    assert hits, f"no document quotes {name} in the form {_DOCUMENTED_AS[name]!r}"
    expected = _numeric_defaults()[name]
    for path, value in hits:
        assert float(value) == float(expected), (
            f"{path.name} quotes {name} as {value}; `search()` ships {expected}"
        )
