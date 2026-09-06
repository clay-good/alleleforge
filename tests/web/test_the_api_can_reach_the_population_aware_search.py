"""The project's differentiating capability was unreachable over HTTP.

`OffTargetRequest` accepts `populations` and `maf`. It accepts no population source,
`create_app` took none, and no environment variable supplied one — so every scan the API
ran was reference-only, whatever ancestry labels a client asked for, and every ancestry
breakdown came back empty. The same gap was found and fixed for the CLI in an earlier
round (`--gnomad`); the web shell kept it.

An empty breakdown reads as "no ancestry-specific risk found" rather than "nothing was
searched", which is the confusion this project exists to prevent — and a client had no way
to discover which of the two they were looking at, because `/api/health` reported only
whether a *reference* was loaded.

The source is operator-configured, like the reference genome: a client-supplied path would
be an arbitrary file read on the server. `create_app(gnomad=...)` or
`ALLELEFORGE_GNOMAD_TSV`, and `/api/health` says which deployment a client is talking to.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alleleforge.data.gnomad import GnomadDB
from alleleforge.web.api.app import create_app

SPACER = "GACCATGCAACCTTGAACGT"


@pytest.fixture
def bias_case(tmp_path: Path) -> tuple[Path, Path]:
    """The rs114518452-style case: no PAM in the reference, an AFR allele creates one."""
    fasta = tmp_path / "bias.fa"
    fasta.write_text(">chr2\n" + "T" * 10 + SPACER + "CGT" + "T" * 10 + "\n")
    sites = tmp_path / "bias.tsv"
    sites.write_text(
        "#chrom\tpos\tref\talt\taf\tafr\tamr\teas\tnfe\tsas\n"
        "chr2\t33\tT\tG\t0.03\t0.105\t0.012\t0.0\t0.001\t0.0\n"
    )
    return fasta, sites


def _client(fasta: Path, sites: Path | None) -> TestClient:
    from alleleforge.genome.reference import ReferenceGenome

    return TestClient(
        create_app(
            reference=ReferenceGenome(fasta, build="hg38"),
            gnomad=GnomadDB.from_sites_tsv(sites) if sites is not None else None,
        )
    )


def test_a_configured_source_makes_the_search_population_aware(
    bias_case: tuple[Path, Path],
) -> None:
    fasta, sites = bias_case
    body = (
        _client(fasta, sites)
        .post(
            "/api/offtarget",
            json={"spacer": SPACER, "pam": "NGG", "populations": ["afr", "nfe"]},
        )
        .json()
    )
    assert body["n_sites"] == 1, "the population site the reference-only scan cannot see"
    site = body["report"]["sites"][0]
    assert site["origin"] == "population"
    assert site["ancestries"]["afr"] > site["ancestries"]["nfe"]
    assert body["expected_burden"] == pytest.approx(0.105)


def test_without_a_source_the_same_request_is_blind(bias_case: tuple[Path, Path]) -> None:
    """The behaviour before this change — kept as the contrast, not as a regression."""
    fasta, _sites = bias_case
    body = (
        _client(fasta, None)
        .post(
            "/api/offtarget",
            json={"spacer": SPACER, "pam": "NGG", "populations": ["afr", "nfe"]},
        )
        .json()
    )
    assert body["n_sites"] == 0
    assert "not measured" in body["search_description"] or "no data" in body["search_description"]


def test_health_says_which_deployment_this_is(bias_case: tuple[Path, Path]) -> None:
    """A client cannot supply the source, so it must be able to see whether one exists."""
    fasta, sites = bias_case
    assert _client(fasta, sites).get("/api/health").json()["gnomad_loaded"] is True
    assert _client(fasta, None).get("/api/health").json()["gnomad_loaded"] is False


def test_the_env_var_configures_it(
    bias_case: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The deployment guide's way in: `uvicorn` binds the module app and calls nothing."""
    fasta, sites = bias_case
    monkeypatch.setenv("ALLELEFORGE_REFERENCE_FASTA", str(fasta))
    monkeypatch.setenv("ALLELEFORGE_GNOMAD_TSV", str(sites))
    assert TestClient(create_app()).get("/api/health").json()["gnomad_loaded"] is True


def test_the_report_does_not_tell_an_api_client_to_pass_a_cli_flag(
    bias_case: tuple[Path, Path],
) -> None:
    """`search_description` is returned verbatim over HTTP and rendered into reports.

    It read "pass --gnomad or --haplotypes" — flags that exist on one of the three shells,
    and that an HTTP client or a Python caller cannot pass at all.
    """
    fasta, _sites = bias_case
    body = (
        _client(fasta, None)
        .post(
            "/api/offtarget",
            json={"spacer": SPACER, "pam": "NGG", "populations": ["afr"]},
        )
        .json()
    )
    assert "--gnomad" not in body["search_description"]
    assert "population allele-frequency source" in body["search_description"]


def test_a_configured_haplotype_panel_runs_the_haplotype_pass(tmp_path: Path) -> None:
    """The population source's sibling: wiring one and not the other is the asymmetry.

    The CLI names both in one breath ("pass --gnomad or --haplotypes"), and the
    haplotype-aware pass finds a site that exists only on a *co-inherited combination*
    of alleles — something no single-variant source can nominate.
    """
    from alleleforge.data.haplotypes import HaplotypePanel
    from alleleforge.genome.reference import ReferenceGenome

    fasta = tmp_path / "hap.fa"
    fasta.write_text(">chr2\n" + "T" * 10 + SPACER + "CGT" + "T" * 10 + "\n")
    panel_tsv = tmp_path / "panel.tsv"
    panel_tsv.write_text(
        "#hap_id\tchrom\tstart\tend\tpopulation\tfrequency\tvariants\n"
        "H1\tchr2\t0\t50\tafr\t0.2\tchr2:32:T>G\n"
    )
    client = TestClient(
        create_app(
            reference=ReferenceGenome(fasta, build="hg38"),
            haplotypes=HaplotypePanel.from_tsv(panel_tsv, source=str(panel_tsv)),
        )
    )
    assert client.get("/api/health").json()["haplotypes_loaded"] is True
    body = client.post(
        "/api/offtarget", json={"spacer": SPACER, "pam": "NGG", "populations": ["afr"]}
    ).json()
    assert body["n_sites"] == 1, "the haplotype pass nominated nothing"
    assert body["report"]["sites"][0]["origin"] == "population"


def test_health_reports_an_unconfigured_panel(bias_case: tuple[Path, Path]) -> None:
    fasta, _sites = bias_case
    assert _client(fasta, None).get("/api/health").json()["haplotypes_loaded"] is False
