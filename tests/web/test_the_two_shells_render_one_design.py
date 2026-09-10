"""The cohort table is checked across both shells. The single design was not.

"The library is the source of truth; the CLI and the web are thin shells" is this
project's sixth principle, and the surface it matters most on is the one a reader actually
opens: a single variant's ranked menu. A dozen tests assert pieces of that on either side
— the same fields, the same caveats, the same disclaimer — and none had ever put the two
documents beside each other and diffed them.

Run for real once by hand on a 2 Mb genome, they were byte-identical. That is the check
worth keeping, because the two paths diverge on things no small fixture reaches: a scan
that only a real contig runs, a memo only a second candidate touches, a format written by
one shell and rendered by the other. This file does it on a contig big enough to produce
several candidates and a sub-threshold tail, on every format both shells offer.

The run timestamp is the one thing allowed to differ.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from typer.testing import CliRunner

from alleleforge.cli.main import app as cli_app
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.web.api.app import create_app

VARIANT = "chr1:2001:"


@pytest.fixture
def deployment(tmp_path: Path) -> tuple[FastAPI, Path, str]:
    """One genome, served and passed to the CLI, and a variant its bases support."""
    rng = random.Random(20240501)
    sequence = "".join(rng.choices("ACGT", k=20_000))
    fasta = tmp_path / "shared.fa"
    fasta.write_text(">chr1\n" + sequence + "\n")
    ref_base = sequence[2000]
    variant = f"{VARIANT}{ref_base}>{'A' if ref_base != 'A' else 'G'}"
    return create_app(reference=ReferenceGenome(fasta, build="hg38")), fasta, variant


def _cli(fasta: Path, variant: str, fmt: str, tmp_path: Path) -> str:
    out = tmp_path / f"cli.{fmt}"
    result = CliRunner().invoke(
        cli_app,
        [
            "design",
            variant,
            "--reference-fasta",
            str(fasta),
            "--format",
            fmt,
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    return out.read_text(encoding="utf-8")


async def _web(app: FastAPI, variant: str, fmt: str) -> str:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(f"/api/design?format={fmt}", json={"variant": variant})
    assert response.status_code == 200, response.text
    return response.text


def _without_the_clock(payload: Any) -> Any:
    """Strip what a run is allowed to differ on: when it happened."""
    if isinstance(payload, dict):
        return {
            key: _without_the_clock(value)
            for key, value in payload.items()
            if key not in {"timestamp", "generated"}
        }
    if isinstance(payload, list):
        return [_without_the_clock(item) for item in payload]
    return payload


@pytest.mark.anyio
async def test_the_json_report_is_the_same_document(
    deployment: tuple[FastAPI, Path, str], tmp_path: Path
) -> None:
    app, fasta, variant = deployment
    from_cli = json.loads(_cli(fasta, variant, "json", tmp_path))
    from_web = json.loads(await _web(app, variant, "json"))
    assert from_cli["candidates"], "the fixture produced no candidates; this would be vacuous"
    assert _without_the_clock(from_cli) == _without_the_clock(from_web)


@pytest.mark.anyio
async def test_the_flat_table_is_the_same_document(
    deployment: tuple[FastAPI, Path, str], tmp_path: Path
) -> None:
    """The surface a pipeline reads, including its `#` note block."""
    app, fasta, variant = deployment
    from_cli = _cli(fasta, variant, "tsv", tmp_path).splitlines()
    from_web = (await _web(app, variant, "tsv")).splitlines()
    strip = lambda lines: [line for line in lines if "generated" not in line]  # noqa: E731
    assert len(from_cli) > 5, from_cli
    assert strip(from_cli) == strip(from_web)


@pytest.mark.anyio
async def test_the_rendered_report_is_the_same_document(
    deployment: tuple[FastAPI, Path, str], tmp_path: Path
) -> None:
    """HTML, where a divergence is what a human would actually see."""
    app, fasta, variant = deployment
    from_cli = _cli(fasta, variant, "html", tmp_path)
    from_web = await _web(app, variant, "html")
    import re

    clock = re.compile(r"\d{4}-\d{2}-\d{2}T[\d:.]+(?:\+00:00|Z)")
    assert len(from_cli) > 1000
    assert clock.sub("<generated>", from_cli) == clock.sub("<generated>", from_web)


@pytest.fixture
def offtarget_deployment(tmp_path: Path) -> tuple[FastAPI, Path, str]:
    """A genome holding the spacer's own locus and two near-matches, so sites exist."""
    spacer = "GACCATGCAACCTTGAACGT"
    near_one = spacer[:9] + "T" + spacer[10:]  # one mismatch
    near_two = spacer[:4] + "A" + spacer[5:15] + "G" + spacer[16:]  # two
    rng = random.Random(31)

    def filler(length: int) -> str:
        return "".join(rng.choices("ACGT", k=length))

    sequence = (
        filler(400)
        + spacer
        + "TGG"
        + filler(400)
        + near_one
        + "AGG"
        + filler(400)
        + near_two
        + "CGG"
        + filler(400)
    )
    fasta = tmp_path / "offtarget.fa"
    fasta.write_text(">chr1\n" + sequence + "\n")
    return create_app(reference=ReferenceGenome(fasta, build="hg38")), fasta, spacer


@pytest.mark.anyio
async def test_the_two_shells_report_one_off_target_search(
    offtarget_deployment: tuple[FastAPI, Path, str],
) -> None:
    """The other flagship surface, whose two payloads are shaped differently on purpose.

    `aforge offtarget --json` flattens the search parameters beside a `description`; the
    API nests them under `report` and names the sentence `search_description`. Two
    envelopes over one set of facts — so the facts are what this compares, and a
    divergence in any of them is two surfaces disagreeing about a genome.
    """
    app, fasta, spacer = offtarget_deployment
    result = CliRunner().invoke(
        cli_app, ["offtarget", spacer, "--reference-fasta", str(fasta), "--json"]
    )
    assert result.exit_code == 0, result.output + result.stderr
    from_cli = json.loads(result.stdout)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/offtarget", json={"spacer": spacer})
    assert response.status_code == 200, response.text
    from_web = response.json()

    assert from_cli["n_sites"] > 0, "the fixture nominated nothing; this would be vacuous"

    # The numbers a reader acts on.
    for field in (
        "n_sites",
        "worst_score",
        "specificity",
        "expected_burden",
        "on_target_excluded",
        "ancestry_stratification",
        "ancestry_expected_burden",
        "effective_matrix",
        "coordinate_system",
    ):
        assert (
            from_cli[field] == pytest.approx(from_web[field])
            if isinstance(from_cli[field], float)
            else from_cli[field] == from_web[field]
        ), field

    # The sentence, and the budget it describes, wherever each shell chose to put them.
    assert from_cli["search"]["description"] == from_web["search_description"]
    for field in (
        "mismatch_threshold",
        "dna_bulge_budget",
        "rna_bulge_budget",
        "cfd_threshold",
        "mit_threshold",
        "resolved_bases",
        "reference_build",
        "pam",
    ):
        assert from_cli["search"].get(field, from_cli.get(field)) == from_web["report"][field], (
            field
        )

    # And the sites themselves: same loci, same scores, same origins. A locus is a string
    # on the command line and an object over HTTP — deliberately, since a client sends
    # regions in that same object shape — so the comparison is of what they denote.
    def locus(value: Any) -> str:
        if isinstance(value, str):
            return value
        return f"{value['chrom']}:{value['start']}-{value['end']}({value['strand']})"

    def summarize(sites: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
        return [
            (locus(site["locus"]), round(site["score"], 6), site["mismatches"], site["origin"])
            for site in sites
        ]

    assert summarize(from_cli["sites"]) == summarize(from_web["report"]["sites"])
