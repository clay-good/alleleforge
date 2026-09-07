"""Four surfaces answer "do you have this dataset?" and only one of them answered it.

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

That was fixed between the two CLI commands, and the guard written for it compared those
two — which is how the same defect stayed on the web. `GET /api/data` returned name,
version, license and `redistributable` and *nothing else*: an HTTP client asking a
deployment what data it has was told, for seven datasets it does not have, that
AlleleForge may redistribute them. `GET /api/data/{name}` returned the raw descriptor,
exactly as `data show` had.

All four now read one derivation in `alleleforge.data.registry`, and all four are checked
here — because a guard written against two of four surfaces is a guard against half the
defect, which is what the first version of this file turned out to be.
"""

from __future__ import annotations

import json
from pathlib import Path

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


def test_the_web_listing_reports_every_availability_fact_the_cli_does() -> None:
    """The surface the original fix never reached."""
    from fastapi.testclient import TestClient

    from alleleforge.web.api.app import create_app

    with TestClient(create_app(reference=None)) as client:
        rows = {row["name"]: row for row in client.get("/api/data").json()["datasets"]}
    assert rows, "GET /api/data listed nothing; this check would be vacuous"

    listed = {row["name"]: row for row in _json("data", "list")["datasets"]}  # type: ignore[union-attr]
    for name, row in rows.items():
        for field in _DERIVED:
            assert field in row, (
                f"GET /api/data omits {field!r} for {name}: an HTTP client is told only "
                "that the licence permits shipping it, not whether it is here"
            )
            assert row[field] == listed[name][field], (
                f"GET /api/data and `aforge data list` disagree on {field!r} for {name}"
            )
        assert row["presence"], f"no presence sentence for {name}"


def test_the_web_detail_view_reports_them_too() -> None:
    from fastapi.testclient import TestClient

    from alleleforge.web.api.app import create_app

    with TestClient(create_app(reference=None)) as client:
        for name in DEFAULT_REGISTRY.names:
            shown = client.get(f"/api/data/{name}").json()
            for field in (*_DERIVED, "presence"):
                assert field in shown, f"GET /api/data/{name} omits {field!r}"
            assert shown["available"] == (name == "doench-2016-cfd"), name


def test_one_derivation_serves_them_all() -> None:
    """The durable half: a fifth surface must not be able to compute its own answer."""
    from alleleforge.data.registry import dataset_status

    cli = Path(__file__).resolve().parents[1] / "src" / "alleleforge" / "cli" / "main.py"
    web = Path(__file__).resolve().parents[1] / "src" / "alleleforge" / "web" / "api" / "app.py"
    for path in (cli, web):
        text = path.read_text(encoding="utf-8")
        assert "dataset_status" in text, f"{path.name} no longer uses the shared derivation"
        assert "cache_path(name).is_file()" not in text, (
            f"{path.name} re-derives whether a dataset is cached instead of asking "
            "dataset_status; that is how four surfaces came to give three answers"
        )
    assert callable(dataset_status)
