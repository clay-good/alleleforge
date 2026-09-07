"""The excuse for keeping reuse off the web API described a switch that did not exist.

When `offtarget_cache` and `genome_index` reached `design()`, the shell-parity guard
demanded a reason the web API does not expose them, and the reason recorded was: reuse
is the operator's call, not the client's — the store and the index live on the server's
disk, so a client asking for either would spend the operator's resources on its own
request. That reasoning holds. What it left out is that no operator could say yes: there
was no argument, no environment variable, no way at all. An allowance that names a
mechanism nobody implemented is the same false record as one that excuses a gap already
closed.

`ALLELEFORGE_OFFTARGET_CACHE` and `ALLELEFORGE_GENOME_INDEX` (or `create_app(...)`) are
that switch, and `GET /api/health` reports which of them a deployment turned on — a
client cannot enable them and otherwise has no way to know why two deployments running
the same code answer at very different speeds.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.cache import OffTargetCache
from alleleforge.web.api.app import create_app

_VARIANT = "chr2:71:A>C"


@pytest.fixture
def cache_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """This test's own cache root — `get_settings()` loads once per process."""
    import alleleforge.config as config

    root = tmp_path / "cache"
    monkeypatch.setattr(config, "_SETTINGS", None)
    monkeypatch.setenv("ALLELEFORGE_CACHE_DIR", str(root))
    return root


@pytest.fixture
def reusing_app(reference: ReferenceGenome, cache_root: Path) -> FastAPI:
    return create_app(reference=reference, offtarget_cache=OffTargetCache())


@pytest.fixture
async def reusing_client(reusing_app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=reusing_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.mark.anyio
async def test_health_names_the_reuse_a_deployment_enabled(
    client: httpx.AsyncClient, reusing_client: httpx.AsyncClient
) -> None:
    plain = (await client.get("/api/health")).json()
    reusing = (await reusing_client.get("/api/health")).json()
    assert plain["scan_reuse"] == []
    assert reusing["scan_reuse"] == ["offtarget-cache"]


@pytest.mark.anyio
async def test_an_enabled_deployment_stores_and_serves_the_same_report(
    reusing_client: httpx.AsyncClient, cache_root: Path
) -> None:
    body = {"variant": _VARIANT, "run_offtarget": True}
    first = (await reusing_client.post("/api/design", json=body)).json()
    assert len(OffTargetCache()) > 0, "an enabled deployment stored no reference scan"
    second = (await reusing_client.post("/api/design", json=body)).json()
    for report in (first, second):
        report.get("provenance", {}).pop("timestamp", None)
    assert second == first, "the run served from the store did not match the cold one"


@pytest.mark.anyio
async def test_a_default_deployment_writes_nothing(
    client: httpx.AsyncClient, cache_root: Path
) -> None:
    """Reuse is off unless the operator turned it on, here as everywhere else."""
    await client.post("/api/design", json={"variant": _VARIANT, "run_offtarget": True})
    assert len(OffTargetCache()) == 0


def test_the_switch_the_allowance_names_exists() -> None:
    """The point of the round: the reason recorded in the parity guard must be true."""
    from alleleforge.web.api import app as web_app

    source = Path(web_app.__file__).read_text(encoding="utf-8")
    for variable in ("ALLELEFORGE_OFFTARGET_CACHE", "ALLELEFORGE_GENOME_INDEX"):
        assert variable in source, f"{variable} is documented as the operator's switch"
    parameters = inspect.signature(create_app).parameters
    for name in ("offtarget_cache", "genome_index"):
        assert name in parameters, (
            f"create_app takes no {name}, so an embedder cannot enable reuse either"
        )
