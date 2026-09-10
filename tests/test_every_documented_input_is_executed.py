"""The documented *inputs* — a JSON body, a config file — were read by nobody.

Four guards in this repository read this project's prose, and a fifth runs the `aforge`
commands it documents. All of them are about what the reader *invokes*. What the reader
**submits** had no check at all:

* the `curl` bodies in `README.md` and `docs/api/web.md`. Every request model sets
  `extra="forbid"`, so a renamed field turns a documented body into a `422` — and the
  request models gained and lost fields three times in the last dozen rounds.
* the `config.toml` in `docs/api/cli.md`. `_load_config` warns on a key it does not know
  and then ignores it, which is the honest behaviour and means a documented key that
  stopped existing produces a warning nobody sees and a run that silently ignores what
  the reader asked for.

The lesson this file comes from was learned the expensive way one round earlier: the
page's variant placeholder had promised a form the API could not parse, and no check on
the *text* of a document could have found it, because the defect was not in the
characters. When the artifact under test is an input, the check has to be an execution.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from alleleforge.cli.main import app
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.web.api.app import create_app

_ROOT = Path(__file__).resolve().parents[1]
_DOCS = [_ROOT / "README.md", *sorted((_ROOT / "docs").rglob("*.md"))]

#: A documented `curl` line and the JSON body under it: the endpoint path, any query
#: string, and the object. Bodies are written on their own `-d '{…}'` line in every one of
#: these documents, which is also how a reader copies them.
_CURL = re.compile(
    r"curl[^\n]*?localhost:8000(?P<path>/api/[\w/]+)(?P<query>\?[^\s']*)?'?[^\n]*\n"
    r"(?:[^\n]*\n)*?[^\n]*-d '(?P<body>\{.*?\})'",
    re.S,
)


def _documented_bodies() -> list[tuple[str, str, str, dict[str, Any]]]:
    found: list[tuple[str, str, str, dict[str, Any]]] = []
    for path in _DOCS:
        for match in _CURL.finditer(path.read_text(encoding="utf-8")):
            body = json.loads(match.group("body"))
            found.append((path.name, match.group("path"), match.group("query") or "", body))
    return found


def _documented_configs() -> list[tuple[str, dict[str, Any]]]:
    found: list[tuple[str, dict[str, Any]]] = []
    for path in _DOCS:
        for block in re.findall(r"```toml\n(.*?)```", path.read_text(encoding="utf-8"), re.S):
            found.append((path.name, tomllib.loads(block)))
    return found


@pytest.fixture
def prime_reference(tmp_path: Path) -> ReferenceGenome:
    """The locus every documented example uses (`chr2:71:A>C`), designable."""
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    fasta = tmp_path / "doc.fa"
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    return ReferenceGenome(fasta, build="hg38")


def test_there_are_documented_inputs_to_execute() -> None:
    bodies, configs = _documented_bodies(), _documented_configs()
    assert len(bodies) >= 3, bodies
    assert configs, "no documented config file found; this check would be vacuous"
    assert any(path == "/api/design" for _, path, _, _ in bodies)


@pytest.mark.parametrize(
    ("source", "path", "query", "body"), _documented_bodies(), ids=lambda v: str(v)[:30]
)
def test_a_documented_request_body_is_accepted(
    prime_reference: ReferenceGenome, source: str, path: str, query: str, body: dict[str, Any]
) -> None:
    """`extra="forbid"` turns a renamed field into a 422 on a body a reader copied."""
    with TestClient(create_app(reference=prime_reference)) as client:
        response = client.post(path + query, json=body)
    assert response.status_code == 200, (source, path, body, response.text[:400])


@pytest.mark.parametrize(("source", "config"), _documented_configs(), ids=lambda v: str(v)[:30])
def test_a_documented_config_file_is_honored(
    prime_reference: ReferenceGenome, tmp_path: Path, source: str, config: dict[str, Any]
) -> None:
    """Every key it sets must reach the run, not a warning the reader never sees."""
    path = tmp_path / "config.toml"
    path.write_text(
        "\n".join(
            f"{key} = {json.dumps(value)}"
            for key, value in config.items()
            if not isinstance(value, dict)
        )
        + "\n"
        + "".join(
            f"\n[{key}]\n" + "".join(f"{k} = {json.dumps(v)}\n" for k, v in value.items())
            for key, value in config.items()
            if isinstance(value, dict)
        )
    )
    result = CliRunner().invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(prime_reference.path),
            "--config",
            str(path),
            "--no-offtarget",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    assert "unknown config key" not in (result.stderr or ""), result.stderr
    snapshot = json.loads(result.stdout)["provenance"]["config_snapshot"]
    if "weights" in config:
        assert snapshot["weights"].keys() == config["weights"].keys()
        for axis, weight in config["weights"].items():
            assert snapshot["weights"][axis] == pytest.approx(weight, abs=1e-6)
    if "max_per_chemistry" in config:
        assert snapshot["max_candidates_per_chemistry"] == config["max_per_chemistry"]
    if "chemistry" in config:
        assert snapshot["chemistries"] == config["chemistry"]
    if "populations" in config:
        assert snapshot["populations"] == config["populations"]
