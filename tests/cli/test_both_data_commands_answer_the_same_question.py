"""`data list` learned what a dataset's licence does not tell you; `data show` did not.

`redistributable` is a licence permission — AlleleForge is allowed to ship this — and
`data list` was once printing it as "vendored", a presence claim, so gnomAD v4.1 (CC0)
read as shipped while no gnomAD data ships at all. That was fixed by deriving four
presence facts and a plain-English line for the table.

`data show`, the command you run when you want *one* dataset's full story, kept dumping
the descriptor: `redistributable: True`, `sha256: None`, `bundled: False`. Every fact
needed is in there and none of the reading is done, so the command answers "can a run
use this right now?" only for someone who already knows that a null checksum means the
registry will not even fetch it. That is the same confusion, one command over, and the
`--json` payload was missing the derived fields too.

The two now share the derivation, so they cannot drift again, and this checks the
sharing rather than the wording: whatever `list` reports for a dataset, `show` reports.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from alleleforge.cli.main import app
from alleleforge.data.registry import DEFAULT_REGISTRY

runner = CliRunner()

_DERIVED = ("redistributable", "bundled", "cached", "available", "fetchable")


def _json(*args: str) -> dict[str, object]:
    result = runner.invoke(app, [*args, "--json"])
    assert result.exit_code == 0, result.output
    payload: dict[str, object] = json.loads(result.stdout)
    return payload


def test_show_reports_every_availability_fact_list_reports() -> None:
    rows = _json("data", "list")["datasets"]
    assert isinstance(rows, list) and rows, "the registry listed nothing; check vacuous"
    for row in rows:
        name = row["name"]
        shown = _json("data", "show", name)
        for field in _DERIVED:
            assert field in shown, (
                f"`data show {name}` omits {field!r}, which `data list` reports — a "
                "client reading one dataset gets less than one reading all of them"
            )
            assert shown[field] == row[field], (
                f"`data show {name}` and `data list` disagree on {field!r}"
            )


def test_show_says_plainly_whether_a_run_can_use_it() -> None:
    """The question someone runs `show` to answer, answered without decoding fields."""
    for name in DEFAULT_REGISTRY.names:
        result = runner.invoke(app, ["data", "show", name])
        assert result.exit_code == 0, result.output
        assert "usable by a run right now:" in result.stdout, name


def test_the_bundled_dataset_is_the_one_reported_usable() -> None:
    """A floor: if everything reported "NO" the line above would be vacuously present."""
    usable = [
        name
        for name in DEFAULT_REGISTRY.names
        if "usable by a run right now: yes" in runner.invoke(app, ["data", "show", name]).stdout
    ]
    assert usable == ["doench-2016-cfd"], (
        f"expected the bundled CFD matrix to be the usable dataset, got {usable}"
    )


def test_a_licence_permission_is_never_worded_as_presence() -> None:
    """The original defect: 'may redistribute' must not read as 'you have this'."""
    result = runner.invoke(app, ["data", "show", "gnomad"])
    assert result.exit_code == 0, result.output
    assert "usable by a run right now: NO" in result.stdout
    assert "Licence: may redistribute" in result.stdout, (
        "the permission and the presence must both be stated, each named for what it is"
    )
