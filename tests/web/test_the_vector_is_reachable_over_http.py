"""A client over HTTP can name the vector its oligos are ordered for.

The cloning scheme decides which Type IIS enzyme every insert is screened against for
a cloning-lethal internal site. It was a Python-only argument, so the CLI and the web
API both screened for BsmBI whatever vector the user actually clones into. The CLI got
`--vector-scheme`; this pins the same reach over HTTP, including the refusal — a `422`
a client cannot act on is worse than a CLI message, since there is no `--help` on the
other end of an HTTP call.
"""

from __future__ import annotations

import httpx
import pytest

from alleleforge.report.oligos import VECTOR_SCHEMES
from alleleforge.web.api.models import VectorSchemeName


@pytest.mark.anyio
async def test_a_request_may_name_its_vector(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/design", json={"variant": "chr2:71:A>C", "vector_scheme": "px330-bbsi"}
    )
    assert response.status_code == 200, response.text
    schemes = {
        c["oligos"]["scheme"]["name"] for c in response.json()["candidates"] if c.get("oligos")
    }
    assert schemes, "no candidate carried oligos — this check would be vacuous"
    # The locus yields pegRNAs, which an sgRNA-only vector cannot receive, so they stay
    # on the pegRNA acceptor and the report says which one each candidate used.
    assert schemes <= set(VECTOR_SCHEMES), schemes


@pytest.mark.anyio
async def test_an_unknown_vector_is_refused_by_naming_the_real_ones(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/design", json={"variant": "chr2:71:A>C", "vector_scheme": "px330"}
    )
    assert response.status_code == 422, response.text
    body = response.text
    for name in VECTOR_SCHEMES:
        assert name in body, name


def test_the_api_offers_exactly_the_schemes_that_exist() -> None:
    """The enum is spelled out for mypy and OpenAPI; nothing else keeps it honest.

    A scheme added to the registry and not here is a vector that exists and cannot be
    requested — the same gap, one level down.
    """
    assert {member.value for member in VectorSchemeName} == set(VECTOR_SCHEMES)
