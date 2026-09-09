"""The reproducibility contract pinned a menu with nothing to rank and nothing to score.

`scripts/reproduce.py` is the R0 honesty contract — "an AlleleForge run is reproducible
from config + seed" — and its docstring says everything that defines the result is kept:
"candidates, scores, intervals, outcomes, **off-targets**". Three of those had no
non-trivial instance in the canonical run.

The scenario was a 20-nt protospacer between two 20-nt poly-T pads: 63 bases. It produced
**one candidate, of one chemistry, over an off-target search that found nothing.** One
candidate cannot be ranked, one chemistry cannot be compared against another, and an empty
site table means every site-level number in a real report — specificity, worst score, the
matrix that scored it — was outside the contract.

That is not a theoretical gap. Two consecutive rounds changed the off-target scan and
reported "reproduce matches golden" as part of the evidence. Making the PAM scanner
consume its match instead of looking ahead — which silently drops every overlapping PAM
anchor, so a guide is reported safer than it is — leaves the old scenario **passing**:

    old scenario   exit 0
    new scenario   exit 1

The scenario now carries flanks that make prime editing eligible and a two-mismatch decoy
of the protospacer with its own PAM, so the menu ranks four candidates across two
chemistries with five nominated off-target sites.

This file pins that coverage as a property. The golden is regenerated with `--update`
whenever a legitimate change moves it, and nothing else would notice if a future
regeneration quietly shrank it back to a run with nothing in it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_GOLDEN = Path(__file__).resolve().parents[1] / "scripts" / "reproduce_golden.json"


def _body() -> dict[str, Any]:
    body: dict[str, Any] = json.loads(_GOLDEN.read_text())["body"]
    return body


def test_the_menu_has_something_to_rank() -> None:
    """One candidate exercises no ordering, no Pareto front and no tie disclosure."""
    assert len(_body()["candidates"]) >= 2


def test_the_menu_spans_more_than_one_chemistry() -> None:
    """Cross-chemistry ranking is the menu's central act and its loudest caveat."""
    chemistries = {candidate["chemistry"] for candidate in _body()["candidates"]}
    assert len(chemistries) >= 2, chemistries


def test_the_pareto_front_is_a_selection_not_the_whole_menu() -> None:
    """A front holding every candidate says nothing about domination."""
    body = _body()
    assert 0 < len(body["pareto_front"]) < len(body["candidates"])


def test_the_run_nominates_a_real_off_target_site() -> None:
    """The gap that let a broken PAM scan through: a search that found nothing pins
    the search *parameters* and not one scored site."""
    sites = [
        site
        for candidate in _body()["candidates"]
        for site in (candidate.get("offtarget") or {}).get("sites", [])
    ]
    assert sites, "the canonical run nominates no off-target site"


def test_a_nominated_site_carries_the_numbers_a_reader_acts_on() -> None:
    """Pinning a site with no score would be the same gap one level down."""
    site = next(
        site
        for candidate in _body()["candidates"]
        for site in (candidate.get("offtarget") or {}).get("sites", [])
    )
    for field in ("score", "score_matrix"):
        assert site.get(field) is not None, (field, sorted(site))
