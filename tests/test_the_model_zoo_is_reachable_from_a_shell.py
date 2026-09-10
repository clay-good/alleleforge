"""The registry that gates every trained model was reachable from Python alone.

`aforge data list/show` and `GET /api/data`/`GET /api/data/{name}` have answered "do you
have this dataset, and may we ship it?" for several phases, all four reading one
derivation so they cannot disagree. The **model** registry — the cards carrying each
model's licence, its intended use, its out-of-scope use, its known failure modes and the
pinned checkpoint hash — had no shell at all.

That is not a symmetry complaint. `--trained-efficiency`, `--trained-outcome`,
`--trained-base-outcome` and `--trained-prime` are consent gates on those cards; the
leaderboard refuses a submission whose card is incomplete; `GET /api/health` lists which
trained models an operator enabled. So a user could opt into a model, and read nothing
about what they were opting into, from any surface this project ships.

The same presence-versus-permission split the dataset surfaces were corrected for applies
here, and one case is sharper: a cached checkpoint with no pinned hash is *not* usable,
because the registry refuses to load an unverifiable artifact exactly as it refuses to
fetch one. "The file is on disk" would be the wrong answer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from alleleforge import config
from alleleforge.cli.main import app
from alleleforge.errors import ChecksumError
from alleleforge.model_zoo.registry import (
    checkpoint_path,
    default_registry,
    model_status,
)
from alleleforge.web.api.app import create_app

runner = CliRunner()

#: The facts every surface must report, not just the one that grew them first.
_DERIVED = ("pinned", "cached", "available", "fetchable", "research_use", "commercial_use")


def _json(*args: str) -> Any:
    result = runner.invoke(app, [*args, "--json"])
    assert result.exit_code == 0, result.output + result.stderr
    return json.loads(result.stdout)


def test_the_listing_covers_every_card() -> None:
    rows = {row["name"] for row in _json("models", "list")["models"]}
    assert rows == set(default_registry().names), rows


def test_show_reports_every_availability_fact_list_reports() -> None:
    rows = _json("models", "list")["models"]
    assert rows, "the registry listed nothing; this check would be vacuous"
    for row in rows:
        shown = _json("models", "show", row["name"])
        for field in _DERIVED:
            assert field in shown, f"`models show {row['name']}` omits {field!r}"
            assert shown[field] == row[field], f"list and show disagree on {field!r}"


def test_show_prints_the_three_honesty_fields() -> None:
    """What the card is *for*: the fields a reader needs before opting in."""
    result = runner.invoke(app, ["models", "show", "rule-set-3"])
    assert result.exit_code == 0, result.output + result.stderr
    for field in ("intended_use", "out_of_scope_use", "known_failure_modes"):
        assert field in result.stdout, field
    assert "usable by a run right now:" in result.stdout


def test_a_licence_permission_is_never_worded_as_presence() -> None:
    """The dataset surfaces' original defect, in the registry that had no surface."""
    result = runner.invoke(app, ["models", "show", "rule-set-3"])
    assert "usable by a run right now: NO" in result.stdout, result.stdout
    assert "Licence: research + commercial use" in result.stdout, result.stdout


@pytest.fixture
def isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A cache root the CLI will read, restored afterwards.

    `aforge --cache-dir` exports `ALLELEFORGE_CACHE_DIR` so every consumer of the
    settings singleton is redirected at once — deliberately, and process-wide, which
    means a test that used it leaked its temporary directory into every later test in
    the same process. (It did: the web listing then reported a planted checkpoint as
    cached.)
    """
    monkeypatch.setenv("ALLELEFORGE_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(config, "_SETTINGS", None)
    return tmp_path


def test_an_unpinned_card_is_not_reported_usable(isolated_cache: Path) -> None:
    """A checkpoint the registry would refuse to load must not read as available.

    Bytes at the cache path are not the answer: `ModelRegistry.checkpoint` raises
    `ChecksumError` for a cached artifact whose card pins no hash, exactly as it refuses
    to fetch one — an out-of-band file dropped there would otherwise load unverified. So
    this puts a file exactly where such a checkpoint would live and requires the surfaces
    to keep saying NO.
    """
    registry = default_registry()
    unpinned = [n for n in registry.names if registry.get(n).checkpoint_sha256 is None]
    assert unpinned, "no unpinned card ships; this check would be vacuous"
    card = registry.get(unpinned[0])
    planted = checkpoint_path(card, isolated_cache)
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.write_bytes(b"not a checkpoint")
    assert model_status(card, isolated_cache)["cached"] is True, "the plant missed the cache path"

    for name in unpinned:
        row = _json("--cache-dir", str(isolated_cache), "models", "show", name)
        assert row["available"] is False, name
        assert "no pinned checksum" in row["presence"], name


def test_the_registry_itself_refuses_the_planted_checkpoint(tmp_path: Path) -> None:
    """The claim the line above rests on, from the code that would do the loading."""
    registry = default_registry()
    name = next(n for n in registry.names if registry.get(n).checkpoint_sha256 is None)
    card = registry.get(name)
    planted = checkpoint_path(card, tmp_path)
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.write_bytes(b"not a checkpoint")
    with pytest.raises(ChecksumError):
        registry.checkpoint(name, cache_dir=planted.parent)


def test_the_web_surfaces_report_the_same_facts() -> None:
    """The surface the dataset fix reached only on its second attempt."""
    listed = {row["name"]: row for row in _json("models", "list")["models"]}
    with TestClient(create_app(reference=None)) as client:
        rows = {row["name"]: row for row in client.get("/api/models").json()["models"]}
        assert rows, "GET /api/models listed nothing; this check would be vacuous"
        for name, row in rows.items():
            for field in _DERIVED:
                assert field in row, f"GET /api/models omits {field!r} for {name}"
                assert row[field] == listed[name][field], f"{field!r} disagrees for {name}"
            assert row["presence"], name
        detail = client.get("/api/models/rule-set-3").json()
        for field in (*_DERIVED, "intended_use", "out_of_scope_use", "known_failure_modes"):
            assert field in detail, field
        assert client.get("/api/models/nope").status_code == 404


def test_an_unknown_name_is_a_clean_refusal_naming_the_known_ones() -> None:
    result = runner.invoke(app, ["models", "show", "nope"])
    assert result.exit_code != 0
    output = result.output + result.stderr
    assert "unknown model" in output and "rule-set-3" in output
