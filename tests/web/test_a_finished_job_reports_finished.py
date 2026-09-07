"""A failed job reported the running progress value, forever.

`progress` is documented as three values — "0.0 queued, 0.1 running, 1.0 finished" — with
an explicit instruction: *render it as a state, not as a percentage*. A client that
follows that instruction shows "running" for a job that has failed and will never advance,
and a poller keyed on it spins.

    {"state": "error", "progress": 0.1, "error": "unrecognized variant input: ..."}

The 0.1 is assigned on entry to the run and only the success path replaced it. `state`
was right the whole time; the field the documentation tells you to display was not.
"finished" here means terminal — `state` says which kind.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from alleleforge.web.api.models import JobState


async def _run_to_completion(client: httpx.AsyncClient, payload: dict[str, object]) -> dict:
    submitted = await client.post("/api/jobs/design", json=payload)
    assert submitted.status_code == 202, submitted.text
    job_id = submitted.json()["job_id"]
    for _ in range(200):
        await asyncio.sleep(0.01)
        status = (await client.get(f"/api/jobs/{job_id}")).json()
        if status["state"] not in {JobState.PENDING, JobState.RUNNING}:
            return status
    raise AssertionError("job never reached a terminal state")


@pytest.mark.anyio
async def test_a_failed_job_reports_finished(client: httpx.AsyncClient) -> None:
    status = await _run_to_completion(
        client, {"variant": "not-a-variant-at-all", "run_offtarget": False}
    )
    assert status["state"] == JobState.ERROR, status
    assert status["error"], "a failed job must say why"
    assert status["progress"] == 1.0, status


@pytest.mark.anyio
async def test_a_successful_job_still_reports_finished(client: httpx.AsyncClient) -> None:
    status = await _run_to_completion(
        client, {"variant": "chr2:71:A>C", "run_offtarget": False, "max_per_chemistry": 2}
    )
    assert status["state"] == JobState.DONE, status
    assert status["progress"] == 1.0, status
    assert status["result"], "a finished job must carry its report"


@pytest.mark.anyio
async def test_progress_never_stalls_below_one_in_a_terminal_state(
    client: httpx.AsyncClient,
) -> None:
    """The property, stated once: terminal means finished, whatever kind."""
    for payload in (
        {"variant": "chr2:71:A>C", "run_offtarget": False, "max_per_chemistry": 2},
        {"variant": "not-a-variant-at-all", "run_offtarget": False},
    ):
        status = await _run_to_completion(client, payload)
        assert status["state"] in {JobState.DONE, JobState.ERROR}
        assert status["progress"] == 1.0, (payload, status)


def test_the_documented_meaning_covers_the_failed_case() -> None:
    """The enumeration had three entries and the code produced a fourth situation."""
    from alleleforge.web.api.models import JobStatusResponse

    description = JobStatusResponse.model_fields["progress"].description or ""
    assert "terminal" in description, description
    assert "failed" in description or "error" in description, description
