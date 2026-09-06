"""A caveat that does not describe the thing it is attached to is noise.

`RESEARCH_USE_CORE` was split out in an earlier round because the full disclaimer —
"The candidates below are ranked, explicitly uncertain computational hypotheses" — was
being reused verbatim on a leaderboard of *models*, where there are no candidates below.
The comment above the constant says exactly that.

Found by starting the API as `docs/deployment.md` documents and reading the responses:

    GET /api/health -> {"status": "ok", ..., "disclaimer": "... The candidates below are
    ranked ... Every off-target nomination is computational and must be experimentally
    validated ..."}

A liveness probe, promising validation of off-target nominations it does not make, about
candidates it does not have. The standalone off-target surfaces had the mirror-image
problem: they nominate sites and rank no candidates, so the validation sentence is exactly
right and the ranked-candidates sentence describes a menu that is not on the page.

Three wordings now, one per shape of artifact. This pins each surface to the one that
describes it, and — the part that matters — that every one of them still carries the
core research-use sentence.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from alleleforge.cli.main import app as cli_app
from alleleforge.report.builder import (
    RESEARCH_USE_CORE,
    RESEARCH_USE_DISCLAIMER,
    RESEARCH_USE_OFFTARGET,
)

_RANKED = "candidates below are ranked"
_VALIDATE = "must be experimentally validated"


def test_the_three_wordings_nest() -> None:
    """Every artifact keeps the core sentence; the wordings differ only in what follows."""
    for wording in (RESEARCH_USE_DISCLAIMER, RESEARCH_USE_OFFTARGET):
        assert wording.startswith(RESEARCH_USE_CORE)
    assert _RANKED not in RESEARCH_USE_CORE and _VALIDATE not in RESEARCH_USE_CORE
    assert _RANKED not in RESEARCH_USE_OFFTARGET and _VALIDATE in RESEARCH_USE_OFFTARGET
    assert _RANKED in RESEARCH_USE_DISCLAIMER and _VALIDATE in RESEARCH_USE_DISCLAIMER


def test_health_promises_only_what_it_delivers() -> None:
    from alleleforge.web.api.app import create_app

    body = TestClient(create_app()).get("/api/health").json()
    assert RESEARCH_USE_CORE in body["disclaimer"]
    assert _RANKED not in body["disclaimer"]
    assert _VALIDATE not in body["disclaimer"]


def test_the_offtarget_surfaces_drop_the_ranked_candidates_sentence(tmp_path: object) -> None:
    from pathlib import Path

    from alleleforge.web.api.app import create_app

    assert isinstance(tmp_path, Path)
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "ACGT" * 40 + "\n")

    result = CliRunner().invoke(
        cli_app,
        ["offtarget", "GACCATGCAACCTTGAACGT", "--reference-fasta", str(fasta), "--json"],
    )
    assert result.exit_code in (0, 4), result.output
    payload = json.loads(result.stdout)
    assert RESEARCH_USE_CORE in payload["disclaimer"]
    assert _RANKED not in payload["disclaimer"]
    assert _VALIDATE in payload["disclaimer"]

    schema = TestClient(create_app()).get("/openapi.json").json()
    served = schema["components"]["schemas"]["OffTargetResponse"]["properties"]["disclaimer"]
    assert _RANKED not in served["default"]
    assert _VALIDATE in served["default"]
