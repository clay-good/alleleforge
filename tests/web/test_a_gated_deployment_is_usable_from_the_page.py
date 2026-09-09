"""A token-protected deployment served a page that could not do anything.

`ALLELEFORGE_API_TOKEN` gates every `/api/*` call except health — which is right,
and is what `docker-compose.yml` tells an operator to set before publishing the port
beyond the host. The served page is not exempt and cannot guess: it loaded, read
health, listed this deployment's capabilities, and then answered every action with
`401 missing or invalid API token`. Accurate, and nothing a person in a browser can
act on, since a browser cannot add a header by itself. The one audience with no
terminal to fall back to was the one audience locked out.

Health is the endpoint the gate lets through, so it is the only place the page can
learn that it needs to ask. It now reports `auth_required` — never the token — and
the page reveals a field, holds what is typed for the tab, and sends it on every
call through one `apiFetch` wrapper, so a call added later cannot skip the header.
"""

from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.web.api.app import create_app

_FRONTEND = Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend"
_APP_JS = (_FRONTEND / "app.js").read_text(encoding="utf-8")
_INDEX = (_FRONTEND / "index.html").read_text(encoding="utf-8")

_TOKEN = "a-token-a-deployment-set"


@pytest.fixture
def gated_app(reference: ReferenceGenome) -> FastAPI:
    return create_app(reference=reference, api_token=_TOKEN)


@pytest.fixture
async def gated_client(gated_app: FastAPI):
    transport = httpx.ASGITransport(app=gated_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.mark.anyio
async def test_health_says_a_token_is_needed(gated_client: httpx.AsyncClient) -> None:
    body = (await gated_client.get("/api/health")).json()
    assert body["auth_required"] is True, body


@pytest.mark.anyio
async def test_health_never_carries_the_token(gated_client: httpx.AsyncClient) -> None:
    """The one endpoint the gate lets through must not leak what it is gating on."""
    response = await gated_client.get("/api/health")
    assert _TOKEN not in response.text, response.text


@pytest.mark.anyio
async def test_an_open_deployment_says_so(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/health")).json()["auth_required"] is False


@pytest.mark.anyio
async def test_the_page_is_served_and_the_api_is_gated(
    gated_client: httpx.AsyncClient,
) -> None:
    """The premise: the page loads, and without the header nothing else works."""
    assert (await gated_client.get("/")).status_code == 200
    refused = await gated_client.post("/api/design", json={"variant": "chr2:71:A>C"})
    assert refused.status_code == 401, refused.text


@pytest.mark.anyio
async def test_the_header_the_page_sends_is_the_one_that_works(
    gated_client: httpx.AsyncClient,
) -> None:
    accepted = await gated_client.post(
        "/api/design",
        json={"variant": "chr2:71:A>C", "run_offtarget": False, "max_per_chemistry": 2},
        headers={"X-API-Token": _TOKEN},
    )
    assert accepted.status_code == 200, accepted.text


def test_every_api_call_on_the_page_goes_through_the_wrapper() -> None:
    """A call added later must not be able to skip the header.

    Health is the one exemption, and it is exempt on the server too — it is how the
    page finds out a token is needed at all.
    """
    bare = [
        call
        for call in re.findall(r"(?<!api)(?<!api)\bfetch\(\s*[\"\'`]([^\"\'`]+)", _APP_JS)
        if call.startswith("/api/") and call != "/api/health"
    ]
    assert bare == [], f"{len(bare)} API call(s) bypass apiFetch(): {bare}"
    assert "apiFetch(" in _APP_JS
    assert '"X-API-Token"' in _APP_JS


def test_health_is_still_fetched_without_the_wrapper() -> None:
    """Health is the endpoint the gate exempts; it is how the page learns to ask."""
    assert 'fetch("/api/health")' in _APP_JS


def test_the_page_has_somewhere_to_put_the_token() -> None:
    assert 'id="api-token"' in _INDEX, "no token field on the page"
    assert 'id="auth"' in _INDEX
    assert 'type="password"' in _INDEX, "the token field must not be a plain text input"
    assert "hidden" in _INDEX.split('id="auth"')[1][:200], "the panel must start hidden"


def test_the_token_is_held_for_the_tab_not_the_profile() -> None:
    """The operator's secret; the smaller promise is the right one.

    Checked against the calls, not the prose: the comment explaining the choice names
    `localStorage`, and a check that greps the whole file reads its own rationale as
    the violation.
    """
    assert "sessionStorage.setItem(" in _APP_JS
    assert "localStorage.setItem(" not in _APP_JS
    assert "localStorage.getItem(" not in _APP_JS
