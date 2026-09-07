"""The consequence annotator reached the CLI and stopped there.

`--vep` gave a command-line user the variant's predicted molecular consequence and the
caution that an intent to correct targets a variant of modifier impact. Over HTTP there
was no way to ask, which is the asymmetry this project keeps finding: one shell reaches
a capability of the library and the other does not.

The web shell cannot copy the flag, though, and the difference is the point. `--vep` is
its own consent because the person typing it owns the variant. Over HTTP the variant
belongs to the client and the outbound request is made by the *operator's* server, so
the capability is enabled by the operator (`ALLELEFORGE_VEP`) and asked for per request
(`annotate_consequence`). Neither key alone sends anything: a request to a deployment
that has not enabled it is refused, not quietly answered without the annotation.

The API's own description says "no sequence data is transmitted externally". That is
what an OpenAPI client reads to decide whether it may send patient variants here, so a
deployment that enables this must not keep saying it.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.variant.effect import Consequence, Impact, VariantEffect, VepRestPredictor
from alleleforge.web.api.app import create_app

_EFFECT = VariantEffect(
    consequence=Consequence.SPLICE_DONOR,
    impact=Impact.HIGH,
    gene="TESTG",
    transcript="ENST00000000001",
)


@pytest.fixture
def offline_vep(monkeypatch: pytest.MonkeyPatch) -> VepRestPredictor:
    """A predictor that answers locally, so no test opens a connection to Ensembl."""
    monkeypatch.setattr(
        VepRestPredictor,
        "predict",
        lambda self, variant, *, transcript="MANE_SELECT": _EFFECT,
    )
    return VepRestPredictor(consent=True)


@pytest.fixture
def vep_app(reference: ReferenceGenome, offline_vep: VepRestPredictor) -> FastAPI:
    """A deployment whose operator has enabled consequence annotation."""
    return create_app(reference=reference, effect=offline_vep)


@pytest.fixture
async def vep_client(vep_app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=vep_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.mark.anyio
async def test_health_says_whether_the_deployment_offers_it(
    client: httpx.AsyncClient, vep_client: httpx.AsyncClient
) -> None:
    """A client has no other way to learn it, and the answer differs per deployment."""
    off = (await client.get("/api/health")).json()
    on = (await vep_client.get("/api/health")).json()
    assert off["vep_enabled"] is False
    assert on["vep_enabled"] is True


@pytest.mark.anyio
async def test_an_unconfigured_deployment_refuses_rather_than_omits(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/resolve", json={"variant": "chr2:71:A>C", "annotate_consequence": True}
    )
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert "ALLELEFORGE_VEP" in str(detail), "the refusal must name what turns it on"


@pytest.mark.anyio
async def test_a_design_carries_the_consequence_when_both_keys_are_turned(
    vep_client: httpx.AsyncClient,
) -> None:
    response = await vep_client.post(
        "/api/design",
        json={"variant": "chr2:71:A>C", "annotate_consequence": True, "run_offtarget": False},
    )
    assert response.status_code == 200, response.text
    assert "splice donor variant" in response.text
    assert "TESTG" in response.text


@pytest.mark.anyio
async def test_the_annotation_is_off_unless_asked_for(vep_client: httpx.AsyncClient) -> None:
    """The operator enabling it must not annotate on a client's behalf."""
    response = await vep_client.post(
        "/api/design", json={"variant": "chr2:71:A>C", "run_offtarget": False}
    )
    assert response.status_code == 200, response.text
    assert "splice donor variant" not in response.text


def test_a_deployment_that_transmits_does_not_claim_it_does_not(
    reference: ReferenceGenome, offline_vep: VepRestPredictor
) -> None:
    plain = create_app(reference=reference)
    assert "no sequence data is transmitted externally" in plain.description

    transmitting = create_app(reference=reference, effect=offline_vep)
    assert "no sequence data is transmitted externally" not in transmitting.description
    assert "annotate_consequence" in transmitting.description, (
        "the description must name the request field that causes the transmission"
    )
