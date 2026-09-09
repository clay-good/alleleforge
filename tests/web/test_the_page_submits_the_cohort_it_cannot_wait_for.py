"""The browser held one connection open for the whole cohort.

`runBatch()` was a single `fetch("/api/batch")`. A cohort is the long operation —
three hundred variants measured 3m 40s — and a browser, or any proxy in front of the
server, closes an idle request long before that. The panel failed exactly on the
cohorts it exists for, and with a `TypeError` from `fetch`, which says nothing about
what happened. For the whole run the status line read `Designing N variant(s)…`.

`POST /api/jobs/batch` (round 400) returns immediately with an id. The page submits
there and polls, so the connection is never held, the status line carries the job's
state, and a run that outlives any timeout still lands.

The checks read `app.js` as source, like this suite's other page guards: there is no
JavaScript runtime in CI beyond `node --check`. What they pin is the shape of the
call, which is the part that regressed.
"""

from __future__ import annotations

import re
from pathlib import Path

_APP_JS = (
    Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend" / "app.js"
).read_text(encoding="utf-8")


def _body_of(function: str) -> str:
    match = re.search(rf"async function {function}\([^)]*\) \{{(?:.|\n)*?\n\}}", _APP_JS)
    assert match, f"could not find {function}() — this check would be vacuous"
    return match.group(0)


def test_the_cohort_is_submitted_as_a_job() -> None:
    body = _body_of("runBatch")
    assert '"/api/jobs/batch"' in body, body
    assert '"/api/batch"' not in body, (
        "the cohort panel is holding a connection open for the whole run again; "
        "submit to /api/jobs/batch and poll"
    )


def test_the_page_polls_until_the_job_is_terminal() -> None:
    body = _body_of("awaitJob")
    assert "/api/jobs/" in body, body
    for state in ("done", "error"):
        assert f'"{state}"' in body, f"the poll does not handle the {state!r} state"


def test_the_poll_cannot_spin_forever() -> None:
    """A server restart drops in-flight records; the page must not poll into eternity."""
    body = _body_of("awaitJob")
    assert "deadline" in body, body
    assert "Date.now()" in body, body


def test_the_status_line_says_what_the_job_is_doing() -> None:
    """The old panel showed one sentence for the whole run."""
    body = _body_of("runBatch")
    assert "awaitJob(" in body, body
    assert "state" in body, body


def test_the_single_design_is_submitted_as_a_job_too() -> None:
    """The scope line moved, and for a reason that round did not weigh.

    This read "a single design finishes in seconds and renders its own HTML", which is
    true of the *render* and was never the whole cost: each download button then posted
    the entire design again, so looking at the report and saving the PDF, the JSON, the
    menu and the HTML ran it five times — and no two saved files were guaranteed to come
    from the same run. Submitting once and rendering every artifact from the finished job
    fixes both, and is the shape the cohort panel already uses.
    """
    body = _body_of("design")
    assert "/api/jobs/design" in body, body
    assert "awaitJob(" in body, body
    assert '"/api/design?format=html"' not in body, body
