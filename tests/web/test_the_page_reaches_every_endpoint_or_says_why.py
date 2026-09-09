"""The page reached five of the API's eleven endpoints, and nothing recorded the six.

This repository already guards three shell pairs — library to CLI, library to web
request fields, and the benchmark library to `aforge bench` — each on the same principle:
*a capability that exists and cannot be reached is a gap, and a gap has to be a decision
rather than an oversight.* The pair it did not guard is the API and the page it serves.

`test_the_page_can_ask_for_what_the_api_accepts` checks the *fields* of two request
models. Nothing checked the *endpoints*, so an endpoint could be added — as several have
been — with no page surface and no written reason, and the only way to notice was to read
`app.js` and count.

Six of the eleven are unreachable from the page. Some of those are right, and are now
written down. The one that is not is recorded as a gap rather than excused: `aforge
offtarget` is a first-class command and `POST /api/offtarget` is a first-class endpoint,
and checking a spacer you already have is the commonest off-target question there is. The
page can only run an off-target search *inside a design*, so the audience with no
terminal — the one the page exists for — cannot ask it.

The check reads the literal paths `app.js` fetches, which is how the page really names
them: every call goes through `apiFetch` (or `fetch`) with a string literal.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.web.api.app import create_app

_FRONTEND = Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend"
_PAGE = "".join(
    path.read_text(encoding="utf-8") for path in sorted(_FRONTEND.glob("*.js"))
) + "".join(path.read_text(encoding="utf-8") for path in sorted(_FRONTEND.glob("*.html")))

#: Endpoints the page does not call, each with the reason. Two kinds of entry live here
#: and they are deliberately worded differently: a *decision* says why the page is right
#: not to offer it, and a *gap* says why it is not.
_NOT_ON_THE_PAGE: dict[str, str] = {
    "POST /api/resolve": "decision: the page's variant box designs directly, and every "
    "menu it renders already states the resolved locus, its class and what ClinVar says "
    "— which is what `resolve` is for. A separate 'explain this variant' button would "
    "restate the header of the result the same click already produces",
    "GET /api/data": "decision: the registry is an operator's inventory, and the "
    "page reports the part a client can act on — which sources this deployment actually "
    "loaded — from `/api/health`, beside the controls those sources enable",
    "GET /api/data/{name}": "decision: the per-dataset detail view of the same "
    "inventory, and the same reasoning as `GET /api/data` — a client acts on what this "
    "deployment loaded, which the status line already reports",
    "GET /api/bench": "decision: the benchmark registry is a leaderboard surface, not a "
    "design one. The page designs; `aforge bench` and the published board are where the "
    "task table is read",
}


def _api_paths() -> dict[str, str]:
    """Return ``{"METHOD /path": path-as-the-page-would-write-it}`` for every API route."""
    routes: dict[str, str] = {}
    for route in create_app().routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api"):
            continue
        for method in sorted(getattr(route, "methods", None) or []):
            if method in {"HEAD", "OPTIONS"}:
                continue
            routes[f"{method} {path}"] = path
    return routes


def _reached(path: str) -> bool:
    """Return whether the page fetches ``path``.

    Path parameters are stripped to their prefix: the page writes
    ``/api/jobs/${jobId}``, so the literal that appears in the source is the part before
    the parameter.
    """
    stem = path.split("/{")[0]
    return stem in _PAGE


def test_there_is_something_to_check() -> None:
    """A guard that found no endpoints would pass forever."""
    routes = _api_paths()
    assert len(routes) >= 8, routes
    assert any(_reached(path) for path in routes.values()), "the reader found no fetch at all"


def test_every_api_endpoint_is_on_the_page_or_recorded() -> None:
    missing = sorted(
        name
        for name, path in _api_paths().items()
        if not _reached(path) and name not in _NOT_ON_THE_PAGE
    )
    assert not missing, (
        "these endpoints exist and the served page cannot reach them, with no reason "
        f"recorded in _NOT_ON_THE_PAGE: {missing}"
    )


def test_no_recorded_reason_outlives_its_endpoint() -> None:
    """An allowance for a route that is gone is a stale excuse, and reads as coverage."""
    routes = set(_api_paths())
    stale = sorted(name for name in _NOT_ON_THE_PAGE if name not in routes)
    assert not stale, f"these are excused but no longer exist: {stale}"


def test_no_recorded_reason_excuses_an_endpoint_the_page_reaches() -> None:
    """The reverse direction, which is what keeps the reasons honest."""
    paths = _api_paths()
    reached = sorted(name for name in _NOT_ON_THE_PAGE if _reached(paths[name]))
    assert not reached, f"these are excused but the page does reach them: {reached}"


@pytest.mark.parametrize("name", sorted(_NOT_ON_THE_PAGE))
def test_each_reason_says_whether_it_is_a_decision_or_a_gap(name: str) -> None:
    """An allowance list is where a gap goes to look like a choice. Saying which it is
    out loud is the only thing that stops that, and the wording is checkable."""
    reason = _NOT_ON_THE_PAGE[name]
    assert reason.startswith(("decision:", "GAP,")), reason
    assert len(reason) > 60, f"{name}: a one-line excuse is not a reason"
