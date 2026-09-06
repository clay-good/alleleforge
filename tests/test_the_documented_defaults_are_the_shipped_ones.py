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
