"""The changelog must be readable as a changelog, not as an append-only log.

Keep a Changelog gives each release one section per change type. `[Unreleased]` had
grown **77** of them — 36 separate `### Fixed` headings, 32 `### Added` — because every
change prepended its own rather than merging into the existing one. Nothing checked it,
and the result is a document in which "what was fixed" cannot be read in one place,
which is the only thing a changelog is for.
"""

from __future__ import annotations

import re
from pathlib import Path

_CHANGELOG = Path(__file__).resolve().parents[1] / "CHANGELOG.md"

#: The change types Keep a Changelog defines, in the order it lists them.
_TYPES = ("Added", "Changed", "Deprecated", "Removed", "Fixed", "Security")


def _sections() -> dict[str, list[str]]:
    """Return ``{release heading: [change-type headings, in order]}``."""
    out: dict[str, list[str]] = {}
    current = ""
    for line in _CHANGELOG.read_text().splitlines():
        if re.fullmatch(r"## .+", line):
            current = line[3:].strip()
            out[current] = []
        elif re.fullmatch(r"### .+", line) and current:
            out[current].append(line[4:].strip())
    return out


def test_each_release_has_at_most_one_section_per_change_type() -> None:
    sections = _sections()
    assert sections, "no release sections found — this check would be vacuous"
    duplicated = {
        release: [t for t in set(types) if types.count(t) > 1]
        for release, types in sections.items()
        if len(types) != len(set(types))
    }
    assert not duplicated, (
        "changelog sections repeat a change type; merge the bullets under one "
        f"heading instead of prepending another: {duplicated}"
    )


def test_change_types_are_the_documented_ones_in_order() -> None:
    """An unrecognized or out-of-order heading is how the merge above gets skipped."""
    for release, types in _sections().items():
        unknown = [t for t in types if t not in _TYPES]
        assert not unknown, f"{release}: unknown change types {unknown}; expected {_TYPES}"
        assert types == sorted(types, key=_TYPES.index), (
            f"{release}: change types out of order {types}; Keep a Changelog lists them as {_TYPES}"
        )
