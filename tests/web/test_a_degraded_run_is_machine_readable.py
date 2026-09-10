"""A design that lost a chemistry to a defect answered `200` with an empty menu.

The CLI exits non-zero when a chemistry contributes nothing for a reason that is not
biology — "a script or a CI job driving this had no way to tell without re-parsing the
summary", as the round that added it put the case. An HTTP client asking for exactly the
same design got `200`, zero candidates, and the reason in a paragraph of prose.

So the reason is a field. `RankedMenu.unavailable` (and the report's copy of it) carries
one note per chemistry that contributed nothing because of a defect in this tool or a
store whose integrity check failed — the same sentences the rationale carries, as data.
Both shells read it now: the CLI's exit code is decided from the field rather than by
grepping its own marker out of its own prose, and a client can branch on an empty list.

An ordinary run leaves it empty, including one where a chemistry simply does not apply to
the variant. That is biology, the rationale explains it, and it is not a degradation.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from alleleforge.design import designer as designer_module
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.web.api.app import create_app


@pytest.fixture
def deployment(tmp_path: Path) -> tuple[Any, str]:
    rng = random.Random(23)
    sequence = "".join(rng.choices("ACGT", k=4000))
    fasta = tmp_path / "degraded.fa"
    fasta.write_text(">chr1\n" + sequence + "\n")
    ref_base = sequence[1500]
    variant = f"chr1:1501:{ref_base}>{'A' if ref_base != 'A' else 'G'}"
    return create_app(reference=ReferenceGenome(fasta, build="hg38")), variant


def test_an_ordinary_run_reports_nothing_unavailable(deployment: tuple[Any, str]) -> None:
    app, variant = deployment
    with TestClient(app) as client:
        body = client.post("/api/design", json={"variant": variant, "run_offtarget": False}).json()
    assert body["candidates"], "the fixture designed nothing; this check would be vacuous"
    assert body["unavailable"] == []


def test_a_defect_in_a_chemistry_is_a_field_not_a_paragraph(
    deployment: tuple[Any, str],
) -> None:
    app, variant = deployment
    original = designer_module.design_prime

    def explode(*args: object, **kwargs: object) -> object:
        raise ZeroDivisionError("a genuine defect")

    designer_module.design_prime = explode  # type: ignore[assignment]
    try:
        with TestClient(app) as client:
            response = client.post("/api/design", json={"variant": variant, "run_offtarget": False})
    finally:
        designer_module.design_prime = original  # type: ignore[assignment]

    body = response.json()
    assert response.status_code == 200, response.text
    assert body["unavailable"], "the run lost a chemistry and said so only in prose"
    assert "ZeroDivisionError" in body["unavailable"][0]
    # And the prose still says it: the field is an addition, not a move.
    assert "ZeroDivisionError" in body["rationale"]


def test_the_field_is_what_the_command_line_decides_its_exit_code_from() -> None:
    """One source for both shells: the CLI used to grep its own marker out of prose."""
    import inspect

    from alleleforge.cli import main as cli_main

    source = inspect.getsource(cli_main.design)
    assert "menu.unavailable" in source
    assert 'DEFECT_NOTE in (menu.rationale or "")' not in source
