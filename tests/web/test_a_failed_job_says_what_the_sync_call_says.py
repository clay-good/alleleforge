"""The same failure read two different ways depending on how it was submitted.

`POST /api/design` with an unparseable variant returns

    422 {"detail": "unrecognized variant input: 'chr2:1050:Z>Q'"}

The identical request through `POST /api/jobs/design` recorded

    "HTTPException: 422: unrecognized variant input: 'chr2:1050:Z>Q'"

— the framework's exception class and an HTTP status glued to the front of the one
sentence a caller can act on, inside the field whose entire job is carrying that sentence.
The status describes the shape of a *response*; a job record is not one, and by the time a
client reads `error` the 422 that never happened is noise.

Found by running the async flow end to end against a real uvicorn (under `TestClient` a
synchronous poll loop starves the worker, and a job that looks stuck there is an artifact
of the probe, not the product — worth stating, because that is what the first run looked
like).

Exceptions without a `detail` keep their type name, which is a real clue when the message
alone is opaque.
"""

from __future__ import annotations

import random
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.web.api.app import create_app

BAD_VARIANT = "chr2:1050:Z>Q"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    rng = random.Random(11)
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "".join(rng.choice("ACGT") for _ in range(3_000)) + "\n")
    return TestClient(create_app(reference=ReferenceGenome(fasta, build="hg38")))


def _job_error(client: TestClient, variant: str) -> str:
    job = client.post("/api/jobs/design", json={"variant": variant}).json()["job_id"]
    for _ in range(100):
        state = client.get(f"/api/jobs/{job}").json()
        if state["state"] not in {"pending", "running"}:
            return str(state["error"])
        time.sleep(0.05)
    pytest.fail("the job never reached a terminal state")


def test_the_job_error_is_the_synchronous_detail(client: TestClient) -> None:
    sync = client.post("/api/design", json={"variant": BAD_VARIANT})
    assert sync.status_code == 422
    assert _job_error(client, BAD_VARIANT) == sync.json()["detail"]


def test_the_job_error_carries_no_http_furniture(client: TestClient) -> None:
    error = _job_error(client, BAD_VARIANT)
    assert "HTTPException" not in error
    assert "422" not in error
    assert BAD_VARIANT in error, "the actionable part must survive the cleanup"
