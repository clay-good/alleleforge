"""The job store's two caps are inclusive: a store exactly at a cap is within budget.

Every existing fixture sat past a cap, never on it, so a mutation sweep could turn
`>` into `>=` on the count cap, the byte cap, and the per-result limit, and the suite
stayed green. On the wrong side of the edge, a server configured for N jobs keeps
N - 1, and a result exactly the advertised size is refused as too large.

Sizes are measured, not guessed: an unbounded manager runs the payload first, and the
caps are then set to exactly what it reported.
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

from alleleforge.web.api.jobs import JobManager, JobRecord, JobState


class _Payload(BaseModel):
    blob: str


def _work() -> _Payload:
    return _Payload(blob="x" * 500)


async def _finish(manager: JobManager) -> JobRecord:
    record = await manager.submit(_work)
    while record.state not in (JobState.DONE, JobState.ERROR):
        await asyncio.sleep(0.001)
    return record


async def _measured() -> int:
    return (await _finish(JobManager())).result_bytes


@pytest.mark.anyio
async def test_a_result_exactly_the_limit_is_retained() -> None:
    size = await _measured()
    record = await _finish(JobManager(max_result_bytes=size))
    assert record.state is JobState.DONE, record.error


@pytest.mark.anyio
async def test_exactly_max_jobs_terminal_records_are_all_kept() -> None:
    manager = JobManager(max_jobs=2)
    first = await _finish(manager)
    second = await _finish(manager)
    assert manager.get(first.id) is first and manager.get(second.id) is second
    third = await _finish(manager)
    assert manager.get(first.id) is None and manager.get(third.id) is third


@pytest.mark.anyio
async def test_results_exactly_filling_the_byte_cap_are_all_kept() -> None:
    size = await _measured()
    manager = JobManager(max_result_bytes=2 * size)
    first = await _finish(manager)
    second = await _finish(manager)
    assert manager.retained_bytes() == 2 * size
    assert manager.get(first.id) is first and manager.get(second.id) is second
