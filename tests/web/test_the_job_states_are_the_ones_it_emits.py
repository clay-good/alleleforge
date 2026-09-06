"""The status contract named a state the system never emits.

`JobStatusResponse.state` was typed `str` and described as "queued | running | done |
error". Nothing emits `queued`: a job starts `pending`. A client that polls until the
state leaves the documented first value waits forever, and because the field was a bare
string the OpenAPI schema said only `type: string` — there was nothing for the prose to
be checked against.

The neighbouring `progress` field carries a docstring explaining that it was typed and
documented precisely so "the shape is visible in the OpenAPI schema rather than inferred
from two observations". The field one line above kept the untyped version, and its prose
had drifted.

Typed as the enum now, so the four values travel in the schema and a generated client can
switch on them. The tests pin the vocabulary to what the state machine actually produces.
"""

from __future__ import annotations

import random
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.web.api.app import create_app
from alleleforge.web.api.models import JobState, JobStatusResponse


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    rng = random.Random(11)
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "".join(rng.choice("ACGT") for _ in range(3_000)) + "\n")
    return TestClient(create_app(reference=ReferenceGenome(fasta, build="hg38")))


def test_the_schema_carries_the_vocabulary(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()["components"]["schemas"]
    assert schema["JobState"]["enum"] == [state.value for state in JobState]


def test_the_field_is_the_enum_not_a_string() -> None:
    """A `str` field would let any value through and document none of them."""
    assert JobStatusResponse.model_fields["state"].annotation is JobState


def test_no_documented_state_is_unemittable() -> None:
    """The bug: prose naming `queued`, which the state machine has no member for."""
    described = JobStatusResponse.model_fields["state"].description or ""
    for word in ("queued",):
        assert word not in described, f"{word!r} is documented and never emitted"


def test_a_real_job_only_ever_reports_declared_states(client: TestClient) -> None:
    job = client.post(
        "/api/jobs/design", json={"variant": "chr2:1050:G>A", "run_offtarget": False}
    ).json()
    assert job["state"] in {state.value for state in JobState}
    for _ in range(100):
        status = client.get(f"/api/jobs/{job['job_id']}").json()
        assert status["state"] in {state.value for state in JobState}
        if status["state"] in {JobState.DONE, JobState.ERROR}:
            break
        time.sleep(0.05)
