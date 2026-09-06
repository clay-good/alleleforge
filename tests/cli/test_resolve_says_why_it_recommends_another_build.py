"""`resolve` recommended a build without ever saying why.

Round 247 wired the ambiguous-region recommendation into the *design* menu, where every
candidate now carries `ambiguous-region:segdup` with a sentence explaining what it means.
`resolve` — the documented debugging aid, the command whose entire job is telling a
caller what their input means — still answered with a bare build name:

    "reference_recommendation": "T2T-CHM13v2"

and the human render, which is what a person actually reads, did not mention it at all.
A build name is an answer with the question removed. `ReferenceRecommendation.reason`
names the regions that triggered it and was consumed by nothing in the package.

What matters is not the recommendation but its cause: a segmental duplication is where a
read cannot be placed uniquely, which is where an off-target search under-reports. Both
shells now say that, and the same locus produces the same statement in each.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from alleleforge.cli.main import app

#: Inside the 1q21 segdup cluster in `HG38_DIFFICULT_REGIONS` — a real hg38 locus, so
#: this exercises the shipped table rather than a fixture.
SEGDUP = "chr1:144500000:A>G"
CLEAN = "chr7:5530600:A>G"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_the_human_render_states_the_cause(runner: CliRunner) -> None:
    result = runner.invoke(app, ["resolve", SEGDUP])
    assert result.exit_code == 0, result.output
    assert "segdup" in result.output
    assert "under-reports" in result.output


def test_the_json_carries_the_reason_beside_the_build(runner: CliRunner) -> None:
    result = runner.invoke(app, ["resolve", SEGDUP, "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["reference_recommendation"] == "T2T-CHM13v2"
    assert "segdup" in payload["reference_recommendation_reason"]


def test_an_ordinary_locus_says_nothing(runner: CliRunner) -> None:
    """A note that always appears is not a note."""
    result = runner.invoke(app, ["resolve", CLEAN])
    assert result.exit_code == 0, result.output
    assert "segdup" not in result.output
    assert "under-reports" not in result.output
    payload = json.loads(runner.invoke(app, ["resolve", CLEAN, "--json"]).stdout)
    assert payload["reference_recommendation"] is None
    assert payload["reference_recommendation_reason"] is None


def test_the_http_endpoint_says_the_same_thing() -> None:
    from alleleforge.web.api.app import create_app

    client = TestClient(create_app())
    body = client.post("/api/resolve", json={"variant": SEGDUP, "build": "hg38"}).json()
    assert body["reference_recommendation"] == "T2T-CHM13v2"
    assert "segdup" in body["reference_recommendation_reason"]

    clean = client.post("/api/resolve", json={"variant": CLEAN, "build": "hg38"}).json()
    assert clean["reference_recommendation_reason"] is None
