"""The HTTP shell was the surface that still leaked pydantic's report.

`errors.reason` was introduced for exactly this and applied to the CLI, the cohort's
per-item error column, the designer's skip note and the job queue. `web/api/app.py`
— the one place a *client* reads the text — was not on the list, so a round later:

    POST /api/offtarget  {"spacer": "...", "pam": "XYZ"}
    {"detail": "1 validation error for PAM\\npattern\\n  Value error, PAM has
     non-IUPAC characters: ['X', 'Z'] [type=value_error, input_value='XYZ',
     input_type=str]\\n    For further information visit https://errors.pydantic.dev/..."}

A client parsing `detail` gets an internal model name, a field, a framework's error
taxonomy and a link to a library it never imported, wrapped around the one sentence
it can show a user.

FastAPI's own *request-schema* 422 — the structured `[{"type": ..., "loc": ...}]`
body — is a different thing and stays: that is the documented contract for a body
that does not match the schema, and a generated client knows its shape. What is
being fixed is the project's own refusals, raised from inside a handler.
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.anyio
async def test_a_refused_pam_is_one_sentence(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/offtarget", json={"spacer": "GCTACACGACCTATAATGAA", "pam": "XYZ"}
    )
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert isinstance(detail, str), detail
    assert "non-IUPAC" in detail, detail
    for machinery in ("validation error", "pydantic", "input_type", "Value error,"):
        assert machinery not in detail, detail


@pytest.mark.anyio
async def test_a_refused_variant_is_one_sentence(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/resolve", json={"variant": "nonsense"})
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert "unrecognized variant input" in detail, detail
    assert "validation error" not in detail, detail


@pytest.mark.anyio
async def test_a_body_that_does_not_match_the_schema_keeps_its_structure(
    client: httpx.AsyncClient,
) -> None:
    """The framework's own 422 is a contract, not a leak; it must not be flattened."""
    response = await client.post("/api/design", json={"variant": "chr2:71:A>C", "weights": 5})
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert isinstance(detail, list), detail
    assert detail[0]["loc"], detail
