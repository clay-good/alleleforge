"""API responses that could state the opposite of the truth with the suite still green.

A mutation sweep of `web/api/app.py` left 8 of 91 mutants alive, and each one would put
a wrong fact in a response rather than crash:

* `/api/resolve` could invert `changes_the_sequence` and `reference_checked`;
* the trained-model refusal could say "Enabled here: none" while naming models that
  *are* enabled, because the only fixtures enabled nothing;
* `GET /api/models/{name}` could answer 404 for every model it knows, because no test
  ever fetched one by name;
* an `offtarget_cache` or `genome_index` passed to `create_app` could be dropped for
  the environment's;
* the 503 for a missing reference could lose its explanation;
* a 10-item list echoed back in a validation error could be marked truncated;
* `ALLELEFORGE_GENOME_INDEX` with no reference could try to index nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.web.api.app import _truncate_echoed, create_app


def test_resolve_states_whether_the_edit_changes_the_sequence(
    reference: ReferenceGenome,
) -> None:
    data = (
        TestClient(create_app(reference=reference))
        .post("/api/resolve", json={"variant": "chr2:71:A>C"})
        .json()
    )
    assert data["changes_the_sequence"] is True
    assert data["reference_checked"] is True


def test_resolve_without_a_reference_says_it_did_not_check() -> None:
    response = TestClient(create_app(reference=None)).post(
        "/api/resolve", json={"variant": "chr2:71:A>C"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["reference_checked"] is False


def test_the_refusal_lists_the_models_that_are_enabled(reference: ReferenceGenome) -> None:
    client = TestClient(create_app(reference=reference, trained_models=["trained_outcome"]))
    body = {"variant": "chr2:71:A>C", "run_offtarget": False, "trained_prime": True}
    detail = client.post("/api/design", json=body).json()["detail"]
    assert "Enabled here: ['trained_outcome']" in detail, detail
    bare = TestClient(create_app(reference=reference)).post("/api/design", json=body)
    assert "Enabled here: none" in bare.json()["detail"]


def test_a_known_model_is_served_and_an_unknown_one_is_not() -> None:
    client = TestClient(create_app(reference=None))
    name = client.get("/api/models").json()["models"][0]["name"]
    assert client.get(f"/api/models/{name}").status_code == 200
    assert client.get("/api/models/no-such-model").status_code == 404


def test_an_explicit_cache_and_index_are_the_ones_used() -> None:
    sentinel = object()
    assert create_app(reference=None, offtarget_cache=sentinel).state.offtarget_cache is sentinel
    assert create_app(reference=None, genome_index=sentinel).state.genome_index is sentinel


def test_a_missing_reference_explains_itself() -> None:
    response = TestClient(create_app(reference=None)).post(
        "/api/design", json={"variant": "chr2:71:A>C"}
    )
    assert response.status_code == 503
    assert "No reference genome configured" in response.json()["detail"]


def test_an_echoed_list_is_truncated_only_past_ten_items() -> None:
    assert _truncate_echoed(list(range(10))) == list(range(10))
    assert _truncate_echoed(list(range(11)))[-1] == "… (11 items, truncated)"


def test_a_genome_index_is_not_built_without_a_reference(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ALLELEFORGE_GENOME_INDEX", "1")
    monkeypatch.delenv("ALLELEFORGE_REFERENCE", raising=False)
    assert create_app(reference=None).state.genome_index is None
