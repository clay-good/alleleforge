"""A pipeline scripted against the CLI could not see what a pipeline against HTTP could.

`aforge offtarget --json` builds its payload by naming fields of `OffTargetReport` one at
a time, and had drifted eight fields behind the model. The HTTP response returns the model
itself, so the same script written against `/api/offtarget` could branch on all of them —
which is the shape of asymmetry this project keeps finding, here on the surface most
likely to be automated.

The omissions were not decorative. `unbacked_populations` names the ancestries a caller
asked to stratify by that no loaded source can speak for, which is the only thing
separating "no ancestry-specific risk found" from "nothing was measured".
`subthreshold_placements` and `subthreshold_score_sum` are what the scan found and did not
report, so "0 sites" from a scan with a long sub-threshold tail read exactly like a clean
one. `on_target_excluded_placements` and `ambiguous_spacer_positions` are the other two
routes to a specificity of 1.000 that means nothing.

`search_description()` folds several of them into a sentence the payload did carry — which
a human can read and a pipeline cannot branch on.

The project's rule against rebuilding a shared model field by field exists for exactly
this failure. It is enforced here for a payload: every field of the report reaches the
JSON, or is recorded below with the reason.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app
from alleleforge.types.offtarget import OffTargetReport

runner = CliRunner()

_SPACER = "ACGTAACGTTACGTAACGT"

#: Report fields the payload legitimately renders differently, with the reason.
_RENDERED_ELSEWHERE: dict[str, str] = {
    "sites": "rendered as its own list of per-site dicts at the top level",
    "pam": "top-level, beside `scanned_pam`, since one is what was asked for and the "
    "other what was searched",
    "spacer": "top-level: it identifies the whole document, not the search block",
    "scorer": "top-level, with `score_matrix` and `effective_matrix`",
    "score_matrix": "top-level; see `scorer`",
    "reference_build": "top-level, beside the reference snapshot that pins which genome "
    "the build name refers to",
}


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    seq = "ACGTAACGTTACGTAACGT" + "AGG" + "TTACG" * 40
    path = tmp_path / "ref.fa"
    path.write_text(f">chr1\n{seq}\n", encoding="utf-8")
    return path


def _payload(fasta: Path, *extra: str) -> dict[str, object]:
    result = runner.invoke(
        app, ["offtarget", _SPACER, "--reference-fasta", str(fasta), "--json", *extra]
    )
    assert result.exit_code == 0, result.output
    payload: dict[str, object] = json.loads(result.stdout)
    return payload


def test_every_report_field_reaches_the_json_or_says_why(fasta: Path) -> None:
    payload = _payload(fasta)
    search = payload["search"]
    assert isinstance(search, dict)
    emitted = set(payload) | set(search)
    missing = sorted(set(OffTargetReport.model_fields) - emitted - set(_RENDERED_ELSEWHERE))
    assert not missing, (
        f"the report carries {missing} and `aforge offtarget --json` does not. A pipeline "
        "reading the API can branch on them and one reading the CLI cannot. Add the key, "
        "or record it in _RENDERED_ELSEWHERE with the reason."
    )


def test_the_recorded_exceptions_are_real_fields() -> None:
    stale = sorted(set(_RENDERED_ELSEWHERE) - set(OffTargetReport.model_fields))
    assert not stale, f"reasons recorded for fields the report no longer has: {stale}"


def test_an_unmeasured_ancestry_is_visible_to_a_script(fasta: Path) -> None:
    """The finding that motivated this, asserted end to end rather than by field name."""
    search = _payload(fasta, "--populations", "afr,eur")["search"]
    assert isinstance(search, dict)
    assert search["unbacked_populations"] == ["afr", "eur"], (
        "a script cannot otherwise tell an empty ancestry breakdown from an unmeasured one"
    )
    assert search["available_populations"] == []


def test_what_was_not_reported_is_visible_to_a_script(fasta: Path) -> None:
    search = _payload(fasta, "--cfd-threshold", "0.99")["search"]
    assert isinstance(search, dict)
    assert search["subthreshold_placements"] > 0, (
        "a high threshold hid every site and the payload said nothing was below it"
    )
    assert search["subthreshold_score_sum"] >= 0.0
