"""An identifier a specification names must exist.

The previous round found the capability specs unread by any test and a shipped command
missing from them. That was a *coverage* gap. This is the *referential* one: across
4,400 lines of spec there are 467 backticked tokens — CLI flags, class names, enum
members — and nothing checked that any of them still names something real.

Sweeping them today finds nothing, which is why this exists: it is the same check the
CLI help text got, and the documented snippets after it, pointed at the documents with
the most authority and the least readership. A renamed enum member or a retired flag
would leave a requirement describing a system that is not there, and a requirement is
the last place anyone looks for a typo.

The resolver has to understand enum members, because that is most of what a spec cites:
`ZERO_BASED_HALF_OPEN`, `NOT_PROVIDED`, `PATHOGENIC` and `MODIFIER` are members, not
module-level names, and a check that only walked `dir(module)` would report four false
positives on its first run and be deleted by the second.

`_NOT_IDENTIFIERS` carries what looks like code and is not: restriction sites and PAM
motifs (`GGTCTC`, `TTTT`), and the browser APIs the frontend spec names in order to say
it does not use them.
"""

from __future__ import annotations

import builtins
import enum
import importlib
import pkgutil
import re
from pathlib import Path

import click
import pytest
import typer

import alleleforge
from alleleforge.cli.main import app

_ROOT = Path(__file__).resolve().parents[1]
_SPECS = _ROOT / "openspec" / "specs"

#: Backticked tokens that look like identifiers and are not: DNA and PAM motifs, VCF
#: column values, literal output strings (`UNMAPPED` is what `lift` prints), and the
#: browser APIs `web-api/spec.md` names in order to promise the frontend avoids them.
#: `test_the_exemptions_are_still_cited` keeps this from outliving the tokens — it
#: caught two entries here that I had guessed at rather than read.
_NOT_IDENTIFIERS = {
    "AAAC",
    "ACGTN",
    "CGTCTC",
    "GAAGAC",
    "GGTCTC",
    "TTTT",
    "NGG",
    "NRN",
    "NYN",
    "CLNSIG",
    "PASS",
    "UNMAPPED",
    "WebSocket",
    "Worker",
    "XMLHttpRequest",
}


def _spec_text() -> str:
    return "".join(p.read_text() for p in sorted(_SPECS.rglob("spec.md")))


def _public_names() -> set[str]:
    """Every public module-level name and enum member in the package."""
    names: set[str] = set()
    for module in pkgutil.walk_packages(alleleforge.__path__, "alleleforge."):
        try:
            imported = importlib.import_module(module.name)
        except Exception:  # pragma: no cover - an optional stack is absent
            continue
        for attribute in dir(imported):
            if attribute.startswith("_"):
                continue
            names.add(attribute)
            value = getattr(imported, attribute, None)
            if isinstance(value, type) and issubclass(value, enum.Enum):
                names.update(member.name for member in value)
    return names


def _cli_flags() -> set[str]:
    cli = typer.main.get_command(app)
    flags: set[str] = {"--help"}

    def walk(command: click.Command, ctx: click.Context) -> None:
        flags.update(
            o for p in command.params for o in p.opts + p.secondary_opts if o.startswith("--")
        )
        lister = getattr(command, "list_commands", None)
        if lister is None:
            return
        for name in lister(ctx):
            sub = command.get_command(ctx, name)
            assert sub is not None
            walk(sub, click.Context(sub, parent=ctx))

    walk(cli, click.Context(cli))
    return flags


def test_the_sweep_is_not_vacuous() -> None:
    """Guard the guard: both sides must actually find things."""
    assert len(_spec_text()) > 10_000
    assert len(_public_names()) > 200
    assert "--gnomad" in _cli_flags()


def test_every_flag_the_specs_name_exists() -> None:
    named = set(re.findall(r"`(--[a-z][a-z0-9-]+)`", _spec_text()))
    assert named, "no flags parsed out of the specs"
    missing = sorted(named - _cli_flags())
    assert not missing, f"the specs require CLI flags that do not exist: {missing}"


def test_every_class_or_enum_the_specs_name_exists() -> None:
    cited = {t for t in re.findall(r"`([A-Z][A-Za-z0-9_]{3,40})`", _spec_text())}
    cited -= _NOT_IDENTIFIERS
    # `dir(__builtins__)` inside a module yields the builtins *dict*'s methods, not
    # the builtins; the first version of this reported ValueError and KeyError as
    # undefined.
    cited -= set(dir(builtins)) | {"None", "True", "False", "NaN"}
    # Env vars are checked by `test_documented_env_vars_are_read`, not here.
    cited = {t for t in cited if not t.startswith("ALLELEFORGE_")}
    missing = sorted(cited - _public_names())
    assert not missing, (
        f"the specs name types or enum members that do not exist: {missing}. Either "
        "the code was renamed and the requirement was not, or the token belongs in "
        "_NOT_IDENTIFIERS because it is not an identifier."
    )


@pytest.mark.parametrize("member", ["ZERO_BASED_HALF_OPEN", "NOT_PROVIDED", "PATHOGENIC"])
def test_the_resolver_finds_enum_members(member: str) -> None:
    """The check above is only meaningful because it resolves members, not just modules.

    These three are cited by the specs and are members rather than module-level names;
    a `dir(module)`-only resolver reports them as missing and gets deleted.
    """
    assert member in _public_names()


def test_the_exemptions_are_still_cited() -> None:
    """An exemption for a token no spec mentions is stale, and hides the next one."""
    text = _spec_text()
    stale = sorted(t for t in _NOT_IDENTIFIERS if f"`{t}`" not in text)
    assert not stale, f"_NOT_IDENTIFIERS exempts tokens the specs no longer name: {stale}"
