"""Every menu this API returned was scored by the transparent baseline.

`design()` takes five scorer overrides. The shell-parity guard excused all five from the
web API with "a Python object, not expressible in JSON" — true of the *object*, and the
reason the gap survived, because `aforge design --trained-efficiency` had reached the
same capability all along with a boolean. An excuse that describes the argument's type
rather than the capability behind it passes every sweep.

The gap mattered in the direction that is hardest to notice: the API answered `200` with
a complete, plausible menu, and nothing on it said the numbers came from a weight-free
heuristic rather than from Rule Set 3, Lindel, BE-DICT or DeepPrime — nor that the
trained model was an option.

The split is the one `ALLELEFORGE_VEP` already uses, and for a structurally identical
reason: the weights are a consent-gated download or an external checkout on the
*operator's* disk, so only they can turn one on; which model scores a given run is the
client's choice. `GET /api/health` reports what is enabled, because a client has no other
way to learn it, and asking for one that is not enabled is a 422 — never a silent fall
back to a different model.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.web.api.app import _TRAINED_MODELS, create_app
from alleleforge.web.api.models import BatchRequest, DesignRequest

_FIELDS = sorted(_TRAINED_MODELS)


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr1\n" + "ACGTTGCAAGGCTTACCGTA" * 20 + "\n")
    return ReferenceGenome(fasta, build="hg38")


def test_the_four_opt_ins_are_named_the_same_on_both_shells() -> None:
    """One capability, one vocabulary: the request fields are the CLI's flag names."""
    import typer

    from alleleforge.cli.main import app

    design_params = {p.name for p in typer.main.get_command(app).commands["design"].params}  # type: ignore[attr-defined]
    assert set(_FIELDS) <= design_params, sorted(set(_FIELDS) - design_params)
    for model in (DesignRequest, BatchRequest):
        missing = [f for f in _FIELDS if f not in model.model_fields]
        assert not missing, f"{model.__name__} cannot ask for {missing}"


@pytest.mark.parametrize("field", _FIELDS)
@pytest.mark.parametrize("endpoint", ["/api/design", "/api/batch"])
def test_asking_for_a_model_this_deployment_lacks_is_refused_not_ignored(
    field: str, endpoint: str, reference: ReferenceGenome
) -> None:
    """A baseline-scored menu and a trained-model one are indistinguishable."""
    client = TestClient(create_app(reference=reference))
    body: dict[str, object] = {"run_offtarget": False, field: True}
    body["variants" if endpoint == "/api/batch" else "variant"] = (
        ["chr1:103:G>A"] if endpoint == "/api/batch" else "chr1:103:G>A"
    )
    response = client.post(endpoint, json=body)
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert field in detail and "ALLELEFORGE_TRAINED_MODELS" in detail, detail
    assert "trained_models" in detail, "the refusal should name where to look them up"


def test_health_reports_what_the_operator_enabled(reference: ReferenceGenome) -> None:
    assert (
        TestClient(create_app(reference=reference)).get("/api/health").json()["trained_models"]
        == []
    )
    enabled = ["trained_outcome", "trained_prime"]
    client = TestClient(create_app(reference=reference, trained_models=enabled))
    assert client.get("/api/health").json()["trained_models"] == sorted(enabled)


def test_an_enabled_model_is_no_longer_refused(reference: ReferenceGenome) -> None:
    """The gate opens: same request, same deployment, one operator setting apart."""
    client = TestClient(create_app(reference=reference, trained_models=["trained_outcome"]))
    body = {"variant": "chr1:103:G>A", "run_offtarget": False, "trained_outcome": True}
    assert client.post("/api/design", json=body).status_code == 200
    # And the gate is per model, not a single on/off.
    body_other = {"variant": "chr1:103:G>A", "run_offtarget": False, "trained_prime": True}
    assert client.post("/api/design", json=body_other).status_code == 422


def test_a_typo_in_the_create_app_argument_raises(reference: ReferenceGenome) -> None:
    """A bad literal in Python is a programmer's mistake, and raising is the answer."""
    with pytest.raises(ValueError, match="unknown model"):
        create_app(reference=reference, trained_models=["trained_efficency"])


def test_a_typo_in_the_environment_is_loud_without_being_fatal(
    reference: ReferenceGenome, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A misspelling must not silently enable nothing — and must not stop the container.

    Both halves matter, and the first draft of this feature only had one. `create_app()`
    runs at module scope, so raising on an environment variable takes the whole process
    down at import: `uvicorn alleleforge.web.api.app:app` — the command in the deployment
    guide and the Dockerfile — exits with a traceback and the container never starts.
    That is the defect the reference loader in the same file carries a paragraph about,
    and this round reintroduced it one config source over.

    Loud is now `/api/health`, where every other misconfigured source already reports
    itself, plus a 422 by name on any request for a model that should have been enabled.
    """
    monkeypatch.setenv("ALLELEFORGE_TRAINED_MODELS", "trained_efficency")
    app = create_app(reference=reference)  # must not raise
    client = TestClient(app)
    health = client.get("/api/health").json()

    assert health["trained_models"] == [], health
    error = health["source_errors"]["trained_models"]
    assert "trained_efficency" in error and "trained_efficiency" in error, error

    # And the capability the operator meant to enable is still refused by name.
    response = client.post(
        "/api/design",
        json={"variant": "chr1:103:G>A", "run_offtarget": False, "trained_efficiency": True},
    )
    assert response.status_code == 422, response.text


def test_a_healthy_deployment_reports_no_trained_model_error(
    reference: ReferenceGenome, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The error key must be absent when there is nothing wrong, not present and empty."""
    monkeypatch.setenv("ALLELEFORGE_TRAINED_MODELS", "trained_outcome")
    health = TestClient(create_app(reference=reference)).get("/api/health").json()
    assert health["trained_models"] == ["trained_outcome"]
    assert "trained_models" not in health["source_errors"], health["source_errors"]


def test_the_env_value_all_enables_every_one(
    reference: ReferenceGenome, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALLELEFORGE_TRAINED_MODELS", "1")
    client = TestClient(create_app(reference=reference))
    assert client.get("/api/health").json()["trained_models"] == _FIELDS


def test_the_operator_can_enable_a_subset_by_name_from_the_environment(
    reference: ReferenceGenome, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The comma-separated form is what an operator with one checkout actually sets.

    Only `1` and the typo case were exercised, and this is the branch a deployment
    reaches: BE-DICT checked out and DeepPrime not is an ordinary state, and enabling
    "all four" there would advertise two models the deployment cannot run.
    """
    monkeypatch.setenv("ALLELEFORGE_TRAINED_MODELS", " trained_outcome , trained_prime ")
    client = TestClient(create_app(reference=reference))
    assert client.get("/api/health").json()["trained_models"] == [
        "trained_outcome",
        "trained_prime",
    ]


def test_a_model_enabled_but_not_installable_here_is_a_503_not_a_422(
    reference: ReferenceGenome, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The operator said yes and the deployment cannot deliver: that is not the client's fault.

    Reached by making the adapter fail to *construct*. The shipped adapters all construct
    lazily and fail at weight-load time, where a failure degrades exactly as it does on
    the CLI — so this branch is for the case a model card's licence gate refuses the use,
    and it had no test because nothing in this environment raises there.
    """
    import alleleforge.scoring.cas9_outcome as outcome
    from alleleforge.errors import MissingDependencyError

    def _refuse(**_: object) -> object:
        raise MissingDependencyError("needs a Lindel checkout")

    monkeypatch.setattr(outcome, "LindelAdapter", _refuse)
    client = TestClient(create_app(reference=reference, trained_models=["trained_outcome"]))
    response = client.post(
        "/api/design",
        json={"variant": "chr1:103:G>A", "run_offtarget": False, "trained_outcome": True},
    )
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert "trained_outcome" in detail and "Lindel checkout" in detail, detail
