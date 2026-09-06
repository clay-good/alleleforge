"""A misconfigured deployment reported exactly what an unconfigured one reports.

Each optional data source records why it failed to load — `_GNOMAD_LOAD_ERROR`,
`_HAPLOTYPES_LOAD_ERROR`, and the accessibility tracks' equivalent. Only the reference's
was ever read (through the 503 that `/api/design` raises). The others were set and
consumed by nothing, so:

    ALLELEFORGE_GNOMAD_TSV=/data/typo.tsv  ->  {"gnomad_loaded": false}
    (nothing configured at all)            ->  {"gnomad_loaded": false}

An operator who fat-fingered the path, or shipped a container without the mount, got the
same health response as one who had deliberately configured nothing — on the axis that
decides whether any population site can be nominated at all. This is the class this
project keeps finding ("we did not look" vs "we looked and found nothing"), in code added
three rounds ago.

Found by reading the coverage report for the lines the new code left untested, which is
what pointed at the two variables nothing reads.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alleleforge.web.api.app import create_app


def test_a_bad_population_path_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLELEFORGE_GNOMAD_TSV", str(tmp_path / "does-not-exist.tsv"))
    body = TestClient(create_app()).get("/api/health").json()
    assert body["gnomad_loaded"] is False
    assert "gnomad" in body["source_errors"], "a broken path reads as no path"


def test_an_unconfigured_deployment_reports_no_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """The contrast that makes the field mean something."""
    monkeypatch.delenv("ALLELEFORGE_GNOMAD_TSV", raising=False)
    monkeypatch.delenv("ALLELEFORGE_HAPLOTYPES", raising=False)
    monkeypatch.delenv("ALLELEFORGE_ENCODE_TRACKS", raising=False)
    monkeypatch.delenv("ALLELEFORGE_REFERENCE_FASTA", raising=False)
    body = TestClient(create_app()).get("/api/health").json()
    assert body["gnomad_loaded"] is False
    assert body["source_errors"] == {}


def test_a_bad_haplotype_panel_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    panel = tmp_path / "panel.tsv"
    panel.write_text("#not\tthe\texpected\theader\nrubbish\n")
    monkeypatch.setenv("ALLELEFORGE_HAPLOTYPES", str(panel))
    body = TestClient(create_app()).get("/api/health").json()
    assert body["haplotypes_loaded"] is False
    assert "haplotypes" in body["source_errors"]


def test_a_bad_track_file_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLELEFORGE_ENCODE_TRACKS", str(tmp_path / "missing.bedgraph"))
    body = TestClient(create_app()).get("/api/health").json()
    assert body["chromatin_tracks"] == []
    assert "encode_tracks" in body["source_errors"]
