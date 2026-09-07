"""`--allow-ng` reads as a statement about the run. It is routed to one vertical.

    Fall back to SpCas9-NG (NG PAM) guides when no NGG guide is actionable.

`design()` passes `allow_ng`/`allow_spry` to the SpCas9 nuclease vertical and nowhere
else. Prime and base editing never see them, and prime's decline reason is a bare "no PAM
match at this offset (256)" — so a caller who enabled the flag, got an empty prime menu,
and read that sentence has no way to learn the flag never applied there. The nuclease
vertical, by contrast, names the fallbacks it did not use, which is what made the gap
visible: two chemistries decline for the same reason and only one explains itself.

Extending the fallbacks to prime is a scientific decision, not a bug fix — a PE-NG or
PE-SpRY pegRNA is a different reagent and the efficiency scorers are trained on SpCas9 PE2
— so this states the scope rather than quietly widening it. Same shape as `cell_context`,
which is consumed by prime alone and says so when the other chemistries run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import Chemistry, EditIntent


@pytest.fixture
def pamless(tmp_path: Path) -> ReferenceGenome:
    """A contig with no NGG, NG or NRN PAM: nothing enumerates for any chemistry."""
    path = tmp_path / "flat.fa"
    path.write_text(">chr9\n" + "A" * 400 + "\n")
    return ReferenceGenome(path, build="hg38")


def _menu(reference: ReferenceGenome, **kwargs: object) -> object:
    return design("chr9:200:A>C", reference=reference, run_offtarget=False, **kwargs)


def test_the_fixture_runs_a_vertical_that_never_sees_the_flag(
    pamless: ReferenceGenome,
) -> None:
    menu = _menu(pamless, allow_ng=True)
    assert not menu.candidates
    assert "prime=yes" in menu.rationale, menu.rationale
    assert "cas9_nuclease=no" in menu.rationale, menu.rationale


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"allow_ng": True}, "SpCas9-NG"),
        ({"allow_spry": True}, "SpRY"),
        ({"allow_ng": True, "allow_spry": True}, "SpCas9-NG, SpRY"),
    ],
)
def test_an_inert_fallback_says_it_was_inert(
    pamless: ReferenceGenome, kwargs: dict[str, bool], expected: str
) -> None:
    rationale = _menu(pamless, **kwargs).rationale
    assert "PAM-flexible fallback" in rationale, rationale
    assert expected in rationale, rationale
    assert "SpCas9 nuclease design alone" in rationale


def test_nothing_is_said_when_no_fallback_was_asked_for(pamless: ReferenceGenome) -> None:
    """A note that fires unconditionally is noise."""
    assert "PAM-flexible fallback" not in _menu(pamless).rationale


def test_nothing_is_said_when_the_nuclease_vertical_ran(tmp_path: Path) -> None:
    """It consumed the flag; the nuclease's own decline reason already speaks for it."""
    path = tmp_path / "ko.fa"
    path.write_text(">chr9\n" + "ATATATATAT" * 40 + "\n")
    menu = design(
        "chr9:200:T>C",
        reference=ReferenceGenome(path, build="hg38"),
        run_offtarget=False,
        intent=EditIntent.KNOCK_OUT,
        allow_ng=True,
    )
    assert Chemistry.CAS9_NUCLEASE.value in menu.rationale
    assert "PAM-flexible fallback" not in menu.rationale, menu.rationale


def test_every_shell_that_describes_the_flag_states_its_scope() -> None:
    """The docstring, the CLI help and both request models — one claim, three surfaces."""
    import inspect
    import re

    from alleleforge.cli.main import app
    from alleleforge.web.api.models import BatchRequest, DesignRequest

    scope = "SpCas9 nuclease design alone"

    assert scope in (inspect.getdoc(design) or "")

    import typer

    root = typer.main.get_command(app)
    for command in ("design", "batch"):
        params = root.commands[command].params  # type: ignore[attr-defined]
        helps = [p.help or "" for p in params if "--allow-ng" in getattr(p, "opts", [])]
        assert helps and scope in helps[0], (command, helps)

    for model in (DesignRequest, BatchRequest):
        description = model.model_fields["allow_ng"].description or ""
        assert scope in description, (model.__name__, description)
    assert re.search(r"\S", scope)
