"""A scorer choice must reach the search, and an unsupported one must be refused.

`aforge offtarget --scorer` picks the specificity scorer: `cfd` (the published Doench
2016 matrix), `mit`, or `cfd-cas12a`, which the CLI help says to pair with
`--pam TTTV`. The web request model had no such field, and pydantic's default
behaviour for an unknown key is to **ignore** it, so:

    POST /api/offtarget {"spacer": ..., "scorer": "cfd-cas12a"}   -> 200, scored by CFD

The client asked for one scorer and was silently given another. Worse, `pam` *is*
settable over HTTP, so a Cas12a search was reachable and its result labelled
`doench-2016-cfd` — the published, validated matrix — where the CLI labels the same
run `cas12a-analog-approximation (unvalidated)`. A wrong honesty label is the one
thing this project cannot ship.

The README claims: "Everything that is *data* rather than a path — region scoping, cell
context, the render cap, the on-target locus — is available over HTTP." A scorer name is
data.

The silence is the more general defect, so every API request model now forbids unknown
fields. A client that sends a parameter this server does not support gets a 422 naming
it, rather than a 200 describing a run it did not ask for.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from alleleforge.web.api.app import create_app  # noqa: E402

SPACER = "TATATATATATACCAATATA"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    fasta = tmp_path / "prime.fa"
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    monkeypatch.setenv("ALLELEFORGE_REFERENCE_FASTA", str(fasta))
    return TestClient(create_app())


def test_the_default_scorer_is_the_published_matrix(client: TestClient) -> None:
    """The premise: unasked, the run is CFD and says so."""
    body = client.post("/api/offtarget", json={"spacer": SPACER}).json()
    assert body["effective_matrix"] == "doench-2016-cfd"


def test_a_cas12a_search_is_labelled_as_the_approximation(client: TestClient) -> None:
    """The scorer reaches the search, and the label follows it."""
    response = client.post(
        "/api/offtarget", json={"spacer": SPACER, "pam": "TTTV", "scorer": "cfd-cas12a"}
    )
    assert response.status_code == 200, response.text
    matrix = response.json()["effective_matrix"]
    assert "cas12a" in matrix and "unvalidated" in matrix, matrix


def test_the_mit_scorer_is_reachable(client: TestClient) -> None:
    """MIT is undefined for bulged alignments, so it is asked for without them."""
    body = client.post(
        "/api/offtarget",
        json={"spacer": SPACER, "scorer": "mit", "dna_bulges": 0, "rna_bulges": 0},
    ).json()
    assert body["effective_matrix"] != "doench-2016-cfd"


def test_mit_with_bulges_is_refused_with_its_reason(client: TestClient) -> None:
    """The library's refusal must survive the HTTP boundary, not become a 500."""
    response = client.post("/api/offtarget", json={"spacer": SPACER, "scorer": "mit"})
    assert response.status_code == 422, response.text
    assert "bulged" in response.text


def test_an_unknown_scorer_is_refused(client: TestClient) -> None:
    response = client.post("/api/offtarget", json={"spacer": SPACER, "scorer": "nope"})
    assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    "path, body",
    [
        ("/api/offtarget", {"spacer": SPACER, "not_a_field": 1}),
        ("/api/design", {"variant": "chr2:71:A>C", "populatoins": ["afr"]}),
        ("/api/resolve", {"variant": "chr2:71:A>C", "buidl": "hg38"}),
        ("/api/batch", {"variants": ["chr2:71:A>C"], "intnet": "install"}),
    ],
)
def test_an_unknown_field_is_refused_rather_than_ignored(
    client: TestClient, path: str, body: dict[str, object]
) -> None:
    """A misspelled parameter must not come back as a 200 describing another run."""
    response = client.post(path, json=body)
    assert response.status_code == 422, response.text
    stray = next(k for k in body if k not in ("spacer", "variant", "variants"))
    assert stray in response.text


def test_the_env_var_fixture_is_really_in_effect(client: TestClient) -> None:
    """Guard the guard: without a reference every check above would be a 503."""
    assert os.environ.get("ALLELEFORGE_REFERENCE_FASTA")
    assert client.get("/api/health").json()["reference_loaded"] is True


def test_the_offtarget_response_identifies_the_genome(client: TestClient) -> None:
    """The same document-level context the CLI's `--json` carries, over HTTP.

    A build label is a name the *deployment* chose; the client cannot see the FASTA
    the server opened, which makes this the surface where naming it matters most.
    """
    body = client.post("/api/offtarget", json={"spacer": SPACER}).json()
    assert body["reference"]["contigs"] == 1
    assert len(body["reference"]["sha256"]) == 64
    assert "length" in body["reference"]["pins"]
    assert body["coordinate_system"] == "0-based-half-open"
    assert "not a medical device" in body["disclaimer"]
