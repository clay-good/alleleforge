"""A rejected request must not be echoed back at its own size.

Every string field on these models is bounded -- `variant` at 8192, `spacer` at 512,
`intent` and `cell_context` at 128 -- and none of those bounds constrained the *response*.
FastAPI's default validation error carries the offending `input` verbatim, so a 100 KB
value sent to a field bounded at 128 characters came back as a 100 KB error:

    variant (bounded 8192)      HTTP 422  resp=100152B
    intent (bounded 128)        HTTP 422  resp=100149B
    cell_context (bounded 128)  HTTP 422  resp=100155B
    spacer (bounded 512)        HTTP 422  resp=100149B

The bounds say what is *accepted*; they said nothing about what is *reflected*, and the
field-level fix does not help -- the rejection is what carries the value. So the handler
is the right place, and it covers every field on every model, including ones not written
yet.

The error still has to be usable: a caller needs to see enough of their input to spot a
typo, which is why short values are echoed unchanged and long ones are trimmed with their
real length stated.
"""

from __future__ import annotations

import httpx
import pytest

from alleleforge.web.api.app import MAX_ECHOED_INPUT, _truncate_echoed

#: Far larger than any field's bound, so every case below is a rejection.
OVERSIZED = "x" * 100_000

CASES = {
    "variant": {"variant": OVERSIZED},
    "intent": {"variant": "chr2:71:A>C", "intent": OVERSIZED},
    "cell_context": {"variant": "chr2:71:A>C", "cell_context": OVERSIZED},
}


@pytest.mark.parametrize("field", sorted(CASES))
async def test_an_oversized_field_is_rejected(client: httpx.AsyncClient, field: str) -> None:
    """The premise: each of these really is a validation failure."""
    response = await client.post("/api/design", json=CASES[field])
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("field", sorted(CASES))
async def test_the_response_is_not_the_size_of_the_request(
    client: httpx.AsyncClient, field: str
) -> None:
    response = await client.post("/api/design", json=CASES[field])
    assert len(response.text) < 4096, (
        f"a {len(OVERSIZED)}-character {field} produced a {len(response.text)}-byte error"
    )
    assert OVERSIZED[:1000] not in response.text


async def test_the_offtarget_endpoint_is_covered_too(client: httpx.AsyncClient) -> None:
    """The handler is registered on the app, so a second model needs no second fix."""
    response = await client.post("/api/offtarget", json={"spacer": OVERSIZED})
    assert response.status_code == 422
    assert len(response.text) < 4096


def test_a_short_value_is_shown_in_full() -> None:
    """Guard the guard: trimming must not cost a caller the sight of their own typo.

    Asserted against the helper rather than over HTTP. A short *invalid* string like a
    misspelled intent is accepted by the model -- it is well under the length bound --
    and rejected later by the domain, on a different path that never reaches this
    truncation. Cutting `MAX_ECHOED_INPUT` to 2 left the HTTP version of this test
    green, which is how that was noticed.
    """
    assert _truncate_echoed("corect") == "corect"
    assert _truncate_echoed("x" * MAX_ECHOED_INPUT) == "x" * MAX_ECHOED_INPUT

    trimmed = _truncate_echoed("x" * (MAX_ECHOED_INPUT + 1))
    assert isinstance(trimmed, str)
    assert trimmed.startswith("x" * MAX_ECHOED_INPUT)
    assert f"{MAX_ECHOED_INPUT + 1} characters, truncated" in trimmed


def test_a_long_list_is_trimmed_too() -> None:
    """A thousand-item list reflects as readily as a long string."""
    assert _truncate_echoed(["a", "b"]) == ["a", "b"]
    trimmed = _truncate_echoed([str(n) for n in range(500)])
    assert isinstance(trimmed, list)
    assert len(trimmed) == 11
    assert "500 items, truncated" in trimmed[-1]


async def test_a_domain_rejection_still_names_the_value(client: httpx.AsyncClient) -> None:
    """The other 422 path: a well-formed but unknown intent, rejected by the designer."""
    response = await client.post("/api/design", json={"variant": "chr2:71:A>C", "intent": "corect"})
    assert response.status_code == 422
    assert "corect" in response.text


async def test_the_error_still_names_the_field_and_the_reason(
    client: httpx.AsyncClient,
) -> None:
    """Trimming the value must not cost the parts that make a 422 actionable."""
    response = await client.post("/api/design", json={"variant": OVERSIZED})
    detail = response.json()["detail"]
    assert isinstance(detail, list) and detail, detail
    first = detail[0]
    assert "variant" in first["loc"]
    assert first["msg"]
    assert first["type"]


async def test_a_truncated_value_says_how_long_it_really_was(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/api/design", json={"variant": OVERSIZED})
    body = response.text
    assert f"{len(OVERSIZED)} characters, truncated" in body
    assert str(MAX_ECHOED_INPUT)  # the bound is importable, so a caller can reason about it


async def test_a_valid_request_is_unaffected(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/design", json={"variant": "chr2:71:A>C"})
    assert response.status_code == 200, response.text
