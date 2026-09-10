"""The licence gate existed, was tested, and no shell could set it.

Every model card carries an SPDX-style licence; `ModelUse` is the axis it gates on; and
`ModelRegistry.checkpoint(..., use=...)` raises `LicenseError` for a model whose licence
forbids that use. Every trained adapter takes the same argument. All of it defaulted to
`research`, and neither the CLI nor the web API could pass anything else — so a company
running `aforge design --trained-prime` loaded a research-only checkpoint with no refusal
on any surface, and the gate only ever protected a Python caller who already knew to ask
for it.

`ALLELEFORGE_MODEL_USE` (or `model_use` in the config file) is the operator's declaration.
Not a per-request field: whether these runs are commercial is a fact about who is running
the tool, and a client of a deployment cannot answer it for them.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge import config
from alleleforge.cli.main import app
from alleleforge.config import Settings
from alleleforge.model_zoo import ModelUse, default_registry

runner = CliRunner()


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    path = tmp_path / "prime.fa"
    path.write_text(">chr2\n" + "".join(seq) + "\n")
    return path


@pytest.fixture
def commercial(monkeypatch: pytest.MonkeyPatch) -> None:
    """Declare this machine's runs commercial, and put the setting back afterwards."""
    monkeypatch.setenv("ALLELEFORGE_MODEL_USE", "commercial")
    monkeypatch.setattr(config, "_SETTINGS", None)


def test_the_default_is_research() -> None:
    assert Settings().model_use is ModelUse.RESEARCH


def test_a_research_only_model_is_refused_for_commercial_use(fasta: Path, commercial: None) -> None:
    """The card this fires on is real: DeepPrime ships `research-only`."""
    assert default_registry().get("deepprime").license == "research-only"
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--trained-prime",
            "--reference-fasta",
            str(fasta),
            "--no-offtarget",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    # Not an exception and not silence: the chemistry declines, and the menu's own
    # rationale says which licence stopped which model — the same channel a missing
    # dependency uses, because a refusal a reader cannot see is not a refusal.
    assert "forbids commercial use of model 'deepprime'" in result.stdout


def test_the_same_run_is_not_refused_for_research(fasta: Path) -> None:
    """A floor: without the declaration nothing changed, or the test above proves little."""
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--trained-prime",
            "--reference-fasta",
            str(fasta),
            "--no-offtarget",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    assert "forbids commercial use" not in result.stdout


def test_a_config_file_can_declare_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The other way a machine's operator states a standing fact about their runs."""
    cfg = tmp_path / "config.toml"
    cfg.write_text('model_use = "commercial"\n')
    monkeypatch.delenv("ALLELEFORGE_MODEL_USE", raising=False)
    monkeypatch.setattr(config, "_SETTINGS", None)
    assert Settings.load(config_file=cfg).model_use is ModelUse.COMMERCIAL


def test_a_bad_value_is_a_clean_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLELEFORGE_MODEL_USE", "medical")
    monkeypatch.setattr(config, "_SETTINGS", None)
    with pytest.raises(Exception, match="ALLELEFORGE_MODEL_USE"):
        Settings.load()


def test_the_web_deployment_declares_it_too(fasta: Path, commercial: None) -> None:
    """The operator's fact, on the surface where the operator is not the caller.

    A client cannot say whether the deployment's work is commercial, and must not be
    able to: the declaration belongs to whoever runs the service. So the same request
    that is answered on a research deployment declines the chemistry here, with the
    licence named in the menu's own rationale.
    """
    from fastapi.testclient import TestClient

    from alleleforge.genome.reference import ReferenceGenome
    from alleleforge.web.api.app import create_app

    app_ = create_app(
        reference=ReferenceGenome(fasta, build="hg38"), trained_models=("trained_prime",)
    )
    with TestClient(app_) as client:
        response = client.post(
            "/api/design",
            json={"variant": "chr2:71:A>C", "trained_prime": True, "run_offtarget": False},
        )
    assert response.status_code == 200, response.text
    assert "forbids commercial use of model 'deepprime'" in response.text
    # And the run records what it was declared to be, so a reader of the artifact can
    # tell a research-licensed run from a commercial one months later.
    assert '"model_use":"commercial"' in response.text.replace(" ", "")


def test_the_listing_reports_the_axis_the_gate_uses() -> None:
    """`models list` is where a reader checks a licence before declaring a use."""
    result = runner.invoke(app, ["models", "show", "deepprime"])
    assert result.exit_code == 0, result.output + result.stderr
    assert "research use only" in result.stdout
