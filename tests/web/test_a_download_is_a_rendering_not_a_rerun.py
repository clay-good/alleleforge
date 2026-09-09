"""Five runs of one design, because every download re-POSTed the whole request.

The single-variant panel rendered its report from `POST /api/design?format=html` and then
served each download button from another `POST /api/design?format=…`. So a reader who
looked at the report and saved the PDF, the JSON, the menu and the HTML ran the design
**five times** — five variant resolutions, five enumerations, five off-target scans, which
on a real genome is the expensive part of each one.

Worse than the cost: two files saved side by side were never guaranteed to be the same
run. The PDF on a reader's desk and the JSON beside it came from different invocations,
agreeing on their numbers by determinism rather than by identity, and differing at least
in their timestamps.

The cohort panel had already been moved onto the job route for exactly this reason. The
single-variant panel now does the same: submit once, render every artifact from that
finished job. The job store is bounded and does not survive a restart, so a lost result
falls back to designing again — announced, because it *is* a second run.

Driven in a browser against a live server: four download clicks, four
`GET /api/jobs/<id>/result?format=…`, zero `POST /api/design`, one job id throughout.
"""

from __future__ import annotations

import re
from pathlib import Path

_APP_JS = (
    Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend" / "app.js"
).read_text(encoding="utf-8")


def _function(name: str) -> str:
    match = re.search(rf"async function {name}\([^)]*\)\s*\{{(.*?)\n\}}", _APP_JS, re.S)
    assert match is not None, f"{name} is gone; this guard needs rewriting"
    return match.group(1)


def _uncommented(source: str) -> str:
    return "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("//"))


def test_the_design_is_submitted_as_a_job() -> None:
    """One run per click of Design edits, whatever is downloaded afterwards."""
    source = _uncommented(_function("design"))
    assert "/api/jobs/design" in source, source
    assert "awaitJob" in source, source
    assert "lastDesignJobId" in source, source


def test_a_download_reads_the_finished_job_first() -> None:
    source = _uncommented(_function("download"))
    assert "/api/jobs/${lastDesignJobId}/result?format=${format}" in source, source
    # `/api/design` may still appear — but only after the job result, and only behind a
    # 404, which is the store having forgotten the run rather than the ordinary path.
    if "/api/design" in source:
        assert source.index("lastDesignJobId") < source.index("/api/design"), source
        assert "404" in source[: source.index("/api/design")], source


def test_a_rerun_is_announced_and_finishes_on_a_message() -> None:
    """It is a second run: the file will not match the first on its timestamp."""
    source = _uncommented(_function("download"))
    if "/api/design" not in source:
        return
    assert "no longer holds that run" in source, source
    after = source[source.index("a.click()") :]
    assert "setStatus" in after and "new run" in after, after


def test_the_report_frame_is_rendered_from_the_job_too() -> None:
    """Otherwise the page shows one run and downloads another, which is the same defect."""
    source = _uncommented(_function("design"))
    assert "/result?format=html" in source, source
