"""The page knew the no-egress guarantee was conditional. Two other artifacts did not.

`app.js` conditions the banner on `vep_enabled`, with the reason written beside it: "The
disclaimer promised that no sequence data leaves this deployment. That is the sentence a
reader checks before pasting a patient variant, and enabling the VEP annotation makes it
false." The OpenAPI description branches the same way.

Meanwhile the module's own docstring listed "All compute is local and user-controlled. The
app makes no outbound network call and transmits no sequence data externally" among **two
invariants from the specification**, and the README stated it as a flat guarantee. A
privacy claim is the last place to leave an exception unnamed, and the exception ships:
consequence annotation sends the chromosome, position and both alleles to a public server.

The guard is derived from the feature, not from the wording: while the API can be
configured to annotate consequences, any document making the claim must name the
exception in the same breath. Remove the capability and the guard stops asking.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from alleleforge.web.api.models import DesignRequest
from tests.prose import prose_text
from tests.test_readme_documents_the_cli import _prose_files

_ROOT = Path(__file__).resolve().parents[1]

#: Sentences that assert nothing leaves the deployment.
_CLAIMS = (
    "no sequence data is transmitted externally",
    "transmits **no sequence data externally**",
    "makes no outbound network call",
    "makes **no outbound network call**",
)

#: What must appear near such a claim for it to be true of a configurable deployment.
_EXCEPTION_MARKERS = ("vep", "annotate_consequence", "consequence annotation")


def test_the_capability_that_makes_the_claim_conditional_exists() -> None:
    """The premise: if this goes, the unconditional claim becomes true again."""
    assert "annotate_consequence" in DesignRequest.model_fields


def _blocks(text: str) -> list[str]:
    """Split prose into paragraph-sized blocks — the unit a reader takes in at once."""
    return re.split(r"\n\s*\n", text)


@pytest.mark.parametrize("path", _prose_files(), ids=lambda p: p.name)
def test_a_no_egress_claim_names_its_exception(path: Path) -> None:
    text = prose_text(path)
    offenders = []
    for block in _blocks(text):
        lowered = block.lower()
        if not any(claim.lower() in lowered for claim in _CLAIMS):
            continue
        if not any(marker in lowered for marker in _EXCEPTION_MARKERS):
            offenders.append(block.strip()[:160])
    assert not offenders, (
        f"{path.name} states the no-egress guarantee without naming the one thing that "
        f"can break it (consequence annotation): {offenders}"
    )


def test_the_source_docstring_names_it_too() -> None:
    """The claim's other home: the module that serves the app."""
    source = (_ROOT / "src" / "alleleforge" / "web" / "api" / "app.py").read_text(encoding="utf-8")
    invariants = source[: source.index('"""', source.index('"""') + 3)]
    assert "no outbound" in invariants, invariants[:200]
    assert "ALLELEFORGE_VEP" in invariants, "the module states the invariant with no exception"


def test_the_page_still_conditions_its_banner() -> None:
    """The artifact that had it right, pinned so it stays right."""
    app_js = (_ROOT / "src" / "alleleforge" / "web" / "frontend" / "app.js").read_text(
        encoding="utf-8"
    )
    assert "vep_enabled" in app_js, app_js[:200]
    assert "transmission" in app_js, "the banner is no longer rewritten for a VEP deployment"
