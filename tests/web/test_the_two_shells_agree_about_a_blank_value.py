"""One rule, two implementations, and they have already diverged once.

"A flag given an empty value is not a flag omitted" is enforced by `_refuse_blank_options`
on the command line and by `NonBlank`/`DropBlanks` on the request models. Two expressions of
one rule in two languages, and the second was written by copying the first — which produced
exactly the divergence that shape produces: applied element-wise to a list, it made the
served page refuse `afr,,eas`, a stray comma the CLI has always dropped and run.

A shared implementation is not available (a click option and a pydantic field are different
things), so the agreement is checked behaviourally instead: for each value a shell can
receive, both must reach the same verdict. The population is the values, which is small and
readable; the fields are the ones both shells actually have.

The verdict, not the message: a 422 and an exit code 2 say the same thing in two languages,
and requiring identical prose would be a test of the prose.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

import httpx  # noqa: E402
from typer.testing import CliRunner  # noqa: E402

from alleleforge.cli.main import ExitCode  # noqa: E402
from alleleforge.cli.main import app as cli_app
from alleleforge.genome.reference import ReferenceGenome  # noqa: E402
from alleleforge.web.api.app import create_app  # noqa: E402

pytestmark = pytest.mark.anyio

#: `(flag, request field)` for the options both shells expose. Not derived: the two
#: vocabularies differ by design (`--chemistry` is repeatable, `chemistries` is a list),
#: and a mapping written out is the honest form of "these are the same option".
_SHARED: list[tuple[str, str]] = [
    ("--intent", "intent"),
    ("--cell-context", "cell_context"),
    ("--populations", "populations"),
    ("--chemistry", "chemistries"),
]

#: What a shell can receive in place of a value, and nothing more exotic: these are what a
#: shell script with an unset variable and a reader with a stray comma actually produce.
_VALUES = ["", "   ", "afr,,eas"]


def _cli_accepts(flag: str, value: str, genome: Path) -> bool:
    result = CliRunner().invoke(
        cli_app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(genome),
            "--no-offtarget",
            flag,
            value,
        ],
    )
    return result.exit_code == ExitCode.OK


async def _web_accepts(field: str, value: str, reference: ReferenceGenome) -> bool:
    # A list field receives the same string split the page's own parser applies, so the
    # two shells are given the *same input*, not two readings of it.
    payload: Any = value.split(",") if field in {"populations", "chemistries"} else value
    app = create_app(reference=reference)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/design", json={"variant": "chr2:71:A>C", field: payload})
    return response.status_code == 200


@pytest.fixture
def genome(tmp_path: Path) -> Path:
    path = tmp_path / "g.fa"
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    path.write_text(">chr2\n" + "".join(seq) + "\n")
    return path


@pytest.mark.parametrize(("flag", "field"), _SHARED, ids=lambda v: v)
@pytest.mark.parametrize("value", _VALUES)
async def test_both_shells_reach_the_same_verdict(
    flag: str, field: str, value: str, genome: Path
) -> None:
    reference = ReferenceGenome(genome, build="hg38")
    cli = _cli_accepts(flag, value, genome)
    web = await _web_accepts(field, value, reference)
    assert cli == web, (
        f"{flag}={value!r} is {'accepted' if cli else 'refused'} by the CLI and "
        f"{'accepted' if web else 'refused'} by the API. One rule, two implementations, "
        "and this is the pair that has already diverged once."
    )


async def test_the_values_split_the_verdict(genome: Path) -> None:
    """A table where every row agrees trivially would pass whatever the code did."""
    reference = ReferenceGenome(genome, build="hg38")
    verdicts = {value: await _web_accepts("populations", value, reference) for value in _VALUES}
    assert set(verdicts.values()) == {True, False}, verdicts


def test_each_pair_names_an_option_both_shells_have() -> None:
    """The mapping is written out; this is what stops it from naming a ghost.

    `_SHARED` says "these two are the same option in two vocabularies". Rename either
    side and the row would compare a flag that does not exist against a field that does —
    which passes, because a nonexistent flag is refused by click and a blank field by
    pydantic, and "both refused" is agreement.
    """
    import typer
    from typer._click.types import StringParamType

    from alleleforge.web.api.models import DesignRequest

    root = typer.main.get_command(cli_app)
    design = root.commands["design"]  # type: ignore[attr-defined]
    flags = {
        p.opts[0]
        for p in design.params
        if isinstance(p.type, StringParamType) and p.opts and p.opts[0].startswith("-")
    }
    for flag, field in _SHARED:
        assert flag in flags, f"{flag} is no longer a string option of `aforge design`"
        assert field in DesignRequest.model_fields, f"{field} is no longer a request field"
