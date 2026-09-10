"""The consequence annotation had no error mapping on the web at all.

A round ago `aforge design --vep` learned to report an unreachable Ensembl as
`UNAVAILABLE` with the flag named, instead of raising `requests` at the user. The API
reaches the same predictor through the same resolver and caught only `ValueError`, so
every deliberate failure of that path arrived at the client as:

    500 Internal Server Error

— for an upstream rate limit, for a missing optional dependency, and for a predictor wired
without consent alike. A 500 says "this deployment has a bug". None of these is one, and a
client cannot tell "retry in a minute" from "this server will never do this" from "your
request was wrong" when all three answer the same.

The population is derived: every error type `alleleforge.errors` names is a failure the
library raises **deliberately**, so none of them may reach a client as an unhandled 500.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

import httpx  # noqa: E402

from alleleforge import errors  # noqa: E402
from alleleforge.genome.reference import ReferenceGenome  # noqa: E402
from alleleforge.web.api.app import create_app  # noqa: E402

pytestmark = pytest.mark.anyio

#: The error types reachable from the annotation path. Derived from the module's own
#: `__all__` rather than listed, minus the ones no request can provoke through it:
#: `ChecksumError` is an artifact-integrity failure (its own fail-closed handling) and
#: `ReferenceIndexError` happens at startup, before any request exists.
_UNREACHABLE = {"ChecksumError", "ReferenceIndexError", "reason"}
_ERRORS = [getattr(errors, name) for name in errors.__all__ if name not in _UNREACHABLE]


def test_the_derivation_is_not_empty() -> None:
    assert len(_ERRORS) >= 3, _ERRORS


class _Boom:
    """An effect predictor that fails the way the real one fails."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    def predict(self, variant: Any, transcript: str = "MANE_SELECT") -> Any:
        raise self._exc


def _reference(tmp_path: Path) -> ReferenceGenome:
    fasta = tmp_path / "ref.fa"
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    return ReferenceGenome(fasta, build="hg38")


async def _post(reference: ReferenceGenome, exc: BaseException) -> httpx.Response:
    app = create_app(reference=reference, effect=_Boom(exc))
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        return await c.post(
            "/api/design",
            json={"variant": "chr2:71:A>C", "annotate_consequence": True},
        )


@pytest.mark.parametrize("error_type", _ERRORS, ids=lambda t: t.__name__)
async def test_no_deliberate_error_reaches_the_client_as_a_500(
    error_type: type[BaseException], tmp_path: Path
) -> None:
    response = await _post(_reference(tmp_path), error_type("the annotation failed"))
    assert response.status_code != 500, response.text
    # And it says something: an opaque status is the same failure one layer along.
    assert "the annotation failed" in response.text


async def test_an_unreachable_service_is_retryable_and_a_missing_one_is_not(
    tmp_path: Path,
) -> None:
    """The three cases a client has to be able to tell apart."""
    reference = _reference(tmp_path)

    upstream = await _post(reference, errors.AnnotationServiceError("Ensembl is rate-limiting"))
    assert upstream.status_code == 503  # retry later

    absent = await _post(reference, errors.MissingDependencyError("no requests installed"))
    assert absent.status_code == 501  # this deployment will never do it

    bad_input = await _post(reference, ValueError("unrecognized variant input"))
    assert bad_input.status_code == 422  # your request was wrong
