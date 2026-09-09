"""The web API labelled every genome "hg38", whatever FASTA the operator mounted.

``ALLELEFORGE_REFERENCE_FASTA`` says which *file* to serve. Nothing said which *assembly*
it is, so `_load_reference_from_env` passed the literal ``build="hg38"``, and
``POST /api/design`` resolved every request against the literal ``"hg38"`` as well — while
the CLI has taken ``--build`` since it shipped and stamps whatever the operator says.

A build label is not decoration. It goes into the provenance of every report a researcher
keeps, it is what the off-target engine compares a prebuilt index against, and it is the
answer to the only question that makes a coordinate a locus: the same `chr7:5,530,601` is
a different base in hg38 than in T2T-CHM13. A T2T deployment of this API returned designs
stamped hg38, and its client had no field to state a build in and no way to ask which one
was being served.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.web.api.app import create_app

VARIANT = "chr2:71:A>C"


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    path = tmp_path / "ref.fa"
    path.write_text(">chr2\n" + "".join(seq) + "\n")
    return path


def test_the_env_configured_build_is_the_one_served(fasta: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The operator says which assembly the mounted FASTA is, and it is reported."""
    monkeypatch.setenv("ALLELEFORGE_REFERENCE_FASTA", str(fasta))
    monkeypatch.setenv("ALLELEFORGE_REFERENCE_BUILD", "t2t-chm13v2")
    with TestClient(create_app()) as client:
        health = client.get("/api/health").json()
        assert health["reference_loaded"] is True
        assert health["reference_build"] == "t2t-chm13v2"
        resolved = client.post("/api/resolve", json={"variant": VARIANT}).json()
        assert resolved["build"] == "t2t-chm13v2"


def test_the_default_is_still_hg38(fasta: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Unset means hg38, which is what every existing deployment already assumed."""
    monkeypatch.setenv("ALLELEFORGE_REFERENCE_FASTA", str(fasta))
    monkeypatch.delenv("ALLELEFORGE_REFERENCE_BUILD", raising=False)
    with TestClient(create_app()) as client:
        assert client.get("/api/health").json()["reference_build"] == "hg38"


def test_a_design_carries_the_served_build_not_a_constant(fasta: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The route that hardcoded the label: a report's provenance must name the genome."""
    monkeypatch.setenv("ALLELEFORGE_REFERENCE_FASTA", str(fasta))
    monkeypatch.setenv("ALLELEFORGE_REFERENCE_BUILD", "t2t-chm13v2")
    with TestClient(create_app()) as client:
        body = client.post("/api/design", json={"variant": VARIANT, "run_offtarget": False})
        assert body.status_code == 200, body.text
        blob = body.text
    assert "t2t-chm13v2" in blob, "the design says nothing about the assembly it used"
    assert '"build": "hg38"' not in blob


def test_a_request_for_an_assembly_this_deployment_does_not_serve_is_refused(
    fasta: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """Stating a build the server does not have must not be answered under another one."""
    monkeypatch.setenv("ALLELEFORGE_REFERENCE_FASTA", str(fasta))
    monkeypatch.setenv("ALLELEFORGE_REFERENCE_BUILD", "t2t-chm13v2")
    with TestClient(create_app()) as client:
        for path, payload in (
            ("/api/resolve", {"variant": VARIANT, "build": "hg19"}),
            ("/api/design", {"variant": VARIANT, "build": "hg19", "run_offtarget": False}),
            ("/api/batch", {"variants": [VARIANT], "build": "hg19", "run_offtarget": False}),
        ):
            response = client.post(path, json=payload)
            assert response.status_code == 422, (path, response.text)
            detail = response.json()["detail"]
            assert "t2t-chm13v2" in detail and "hg19" in detail, detail
            assert "reference_build" in detail


def test_an_equivalent_spelling_of_the_served_build_is_accepted(
    fasta: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """`GRCh38` and `hg38` are one assembly; refusing on spelling would be a false alarm."""
    monkeypatch.setenv("ALLELEFORGE_REFERENCE_FASTA", str(fasta))
    monkeypatch.delenv("ALLELEFORGE_REFERENCE_BUILD", raising=False)
    with TestClient(create_app()) as client:
        response = client.post("/api/resolve", json={"variant": VARIANT, "build": "GRCh38"})
        assert response.status_code == 200, response.text


def test_a_programmatic_reference_keeps_its_own_label(fasta: Path) -> None:
    """`create_app(reference=...)` already carried a build; the env path did not."""
    app = create_app(reference=ReferenceGenome(fasta, build="mm39"))
    with TestClient(app) as client:
        assert client.get("/api/health").json()["reference_build"] == "mm39"
        refused = client.post("/api/resolve", json={"variant": VARIANT, "build": "hg38"})
        assert refused.status_code == 422, refused.text


def test_the_page_names_the_assembly_it_is_taking_coordinates_for() -> None:
    """The browser is the audience that cannot read `/api/health` for itself.

    Its status line said "reference loaded", which answers a question nobody asks: the
    box takes a coordinate, and a coordinate without an assembly is not a locus.
    """
    app_js = (
        Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend" / "app.js"
    ).read_text(encoding="utf-8")
    assert "h.reference_build" in app_js
