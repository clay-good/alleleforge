"""`--vep` is the only flag that makes a network call while a design runs, and it had no
handler.

    $ aforge design chr2:71:A>C --reference-fasta g.fa --vep
    [exit 1]
    requests.exceptions.HTTPError: 400 Client Error: Bad Request for url:
    https://rest.ensembl.org/vep/grch38/region/chr2:71-71/C?content-type=application/json

Every way that call fails is somebody else's server on somebody else's network — a 429
from Ensembl's rate limiter, a 503, a timeout, a laptop offline, a locus the assembly does
not have. None of them is a defect in this tool, and all of them arrived as a `requests`
traceback with the query URL in it.

`AnnotationServiceError` names the case, so the CLI can say which flag asked for the
annotation and exit `UNAVAILABLE`, and so a cohort can record it per item: a rate limit two
hundred variants into a five-hundred-variant run is exactly what per-item isolation is for.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app
from alleleforge.design.designer import _EXPECTED_DESIGN_FAILURES
from alleleforge.errors import AnnotationServiceError
from alleleforge.variant.effect import VepRestPredictor

requests = pytest.importorskip("requests")


@pytest.fixture
def genome(tmp_path: Path) -> Path:
    path = tmp_path / "g.fa"
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    path.write_text(">chr2\n" + "".join(seq) + "\n")
    return path


@pytest.mark.parametrize(
    "raised",
    [
        requests.exceptions.HTTPError("429 Client Error: Too Many Requests"),
        requests.exceptions.ConnectionError("Failed to establish a new connection"),
        requests.exceptions.Timeout("Read timed out."),
    ],
)
def test_every_transport_failure_becomes_a_named_error(
    raised: Exception, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_: Any, **__: Any) -> Any:
        raise raised

    monkeypatch.setattr(requests, "get", boom)
    with pytest.raises(AnnotationServiceError) as excinfo:
        VepRestPredictor(consent=True)._default_fetch("https://example.invalid/vep")
    message = str(excinfo.value)
    assert "could not be reached or refused the query" in message
    # The remedy, because a public REST service is not something the reader controls.
    assert "re-run without it" in message


def test_a_body_that_is_not_json_is_the_same_kind_of_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Html:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> Any:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")

    monkeypatch.setattr(requests, "get", lambda *_, **__: _Html())
    with pytest.raises(AnnotationServiceError) as excinfo:
        VepRestPredictor(consent=True)._default_fetch("https://example.invalid/vep")
    assert "not JSON" in str(excinfo.value)


def test_the_cli_names_the_flag_and_exits_unavailable(
    genome: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(self: Any, url: str) -> Any:
        raise AnnotationServiceError("the service at https://x could not be reached")

    monkeypatch.setattr(VepRestPredictor, "_default_fetch", boom)
    result = CliRunner().invoke(
        app, ["design", "chr2:71:A>C", "--reference-fasta", str(genome), "--vep"]
    )
    assert result.exit_code == ExitCode.UNAVAILABLE, result.stderr
    assert "--vep" in result.stderr
    assert "Traceback" not in result.stderr


def test_a_cohort_records_it_per_item_rather_than_calling_it_a_defect() -> None:
    """A rate limit mid-cohort is a per-item data problem, not a bug in this tool."""
    assert AnnotationServiceError in _EXPECTED_DESIGN_FAILURES
