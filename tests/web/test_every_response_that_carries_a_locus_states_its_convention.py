"""The cohort response was the one document whose reader had to assume the convention.

Every coordinate this project prints is 0-based half-open, and a genome browser reads the
same digits as 1-based inclusive — an off-by-one that designs a guide at the wrong place.
So `ResolveResponse`, the design report and `OffTargetResponse` all carry
`coordinate_system`, the CLI's cohort JSON carries the same sentence as `coordinate_note`,
and the four rendered formats state it in their footers.

`BatchResponse` did not. Its rows carry `variant` — the *resolved* variant, which is where
left-alignment has already moved the coordinate and which is printed 0-based — and a
client had nothing in the document to read that against. A cohort is also the artifact most
likely to be forwarded to someone who did not make the request.

The population here is derived from the models: any response whose fields can carry a
locus or a variant must state the convention.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from alleleforge.report.builder import COORDINATE_SYSTEM, DesignReport
from alleleforge.web.api import models as api_models

#: Field names whose value is, or contains, a coordinate this project prints.
_COORDINATE_BEARING = ("locus", "variant", "variants", "report", "items", "candidates")


def _response_models() -> dict[str, type[Any]]:
    """Every `*Response` model the API defines, plus the report the design endpoints embed."""
    found = {
        name: obj
        for name, obj in vars(api_models).items()
        if isinstance(obj, type) and name.endswith("Response") and hasattr(obj, "model_fields")
    }
    found["DesignReport"] = DesignReport
    assert len(found) >= 5, sorted(found)
    return found


def _carries_a_coordinate(model: type[Any]) -> bool:
    return any(field in model.model_fields for field in _COORDINATE_BEARING)


def test_every_coordinate_bearing_response_states_the_convention() -> None:
    silent = sorted(
        name
        for name, model in _response_models().items()
        if _carries_a_coordinate(model) and "coordinate_system" not in model.model_fields
    )
    assert not silent, (
        f"these responses carry a locus or a variant and do not say which convention it "
        f"is in: {silent}. A genome browser reads the same digits as 1-based inclusive."
    )


def test_the_cohort_response_carries_it_end_to_end(tmp_path: Path) -> None:
    """Through the endpoint, not only on the model: a default can be dropped in the call."""
    import random

    from fastapi.testclient import TestClient

    from alleleforge.genome.reference import ReferenceGenome
    from alleleforge.web.api.app import create_app

    rng = random.Random(17)
    sequence = "".join(rng.choices("ACGT", k=3000))
    fasta = tmp_path / "cohort.fa"
    fasta.write_text(">chr1\n" + sequence + "\n")
    ref_base = sequence[1500]
    variant = f"chr1:1501:{ref_base}>{'A' if ref_base != 'A' else 'G'}"

    with TestClient(create_app(reference=ReferenceGenome(fasta, build="hg38"))) as client:
        body = client.post(
            "/api/batch", json={"variants": [variant], "run_offtarget": False}
        ).json()
    assert body["coordinate_system"] == COORDINATE_SYSTEM
    # And the thing it qualifies is really in there.
    assert body["items"][0]["summary"]["variant"].startswith("chr1:1500:")


@pytest.mark.parametrize("name", sorted(_response_models()))
def test_the_convention_is_the_one_string_everything_uses(name: str) -> None:
    """Not a per-model literal: one constant, so two surfaces cannot describe two systems."""
    model = _response_models()[name]
    if "coordinate_system" not in model.model_fields:
        pytest.skip(f"{name} carries no coordinate")
    default = model.model_fields["coordinate_system"].default
    assert default == COORDINATE_SYSTEM, (name, default)
