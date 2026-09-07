"""Thirty-three CLI tests decoded click's mixed stream and called it the JSON output.

`CliRunner`'s `result.output` is stdout *and* stderr interleaved. Thirty-three tests ran
`json.loads(result.output)`, which fails in both directions at once:

* It is not the assertion it looks like. A command that printed a stray line to stdout
  would be caught, but one that wrote its data to stderr, or a note into the middle of a
  pipeline's data stream, would pass — so "the JSON output is well formed" was never
  actually checked on the stream a pipeline reads.
* It breaks on correct changes. This project's convention is that every message about a
  side effect goes to stderr, so adding one — twice in this session, a synthetic-data
  caveat on `bench run` and then on `bench compare` — put a sentence inside the JSON these
  tests decoded, and the failure looked like the feature was broken rather than the test.

`result.stdout` is both the honest assertion and the stable one. This forbids the mixed
stream at the one place where the difference is load-bearing: decoding it as data. Reading
`.output` for a substring is untouched, because a test that wants "this text appeared
somewhere" legitimately wants either stream.
"""

from __future__ import annotations

import re
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_SELF = Path(__file__).name

#: `json.loads(<anything>.output)` — decoding the interleaved stream as structured data.
_DECODES_THE_MIXED_STREAM = re.compile(r"json\.loads?\([^;\n]*\.output\s*\)")


def _offenders() -> list[str]:
    found = []
    for path in sorted(_TESTS.rglob("test_*.py")):
        if path.name == _SELF:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _DECODES_THE_MIXED_STREAM.search(line):
                found.append(f"{path.relative_to(_TESTS)}:{number}")
    return found


def test_the_scan_can_see_the_test_files() -> None:
    """A floor: an empty sweep satisfies the check below without checking anything."""
    files = list(_TESTS.rglob("test_*.py"))
    assert len(files) > 50, f"only found {len(files)} test files"
    assert any("json.loads" in p.read_text(encoding="utf-8") for p in files), (
        "no test decodes JSON at all, so this rule would be vacuous"
    )


def test_no_test_decodes_the_mixed_stream_as_json() -> None:
    offenders = _offenders()
    assert not offenders, (
        "these decode CliRunner's interleaved stdout+stderr as JSON: "
        f"{offenders}. Use `result.stdout` — it is the stream a pipeline reads, so it is "
        "both the assertion that was meant and the one a message on stderr cannot break."
    )
