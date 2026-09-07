"""The build-mismatch refusal offered one remedy, usable by one of three callers.

    source assembly 'hg19' disagrees with requested build 'hg38'; lift the coordinates …
    — `aforge lift <locus> --chain <file> --from hg19 --to hg38`

It is raised in `variant/resolver.py`, so it reaches a Python caller of `resolve()`, a
`aforge design` user, and an HTTP client posting to `/api/design` alike. Only the second
can run that command. A library caller has `Liftover.from_chain_file` and no reason to
shell out; an HTTP client has no shell on the server and there is no lift endpoint.

This is the refusal whose entire purpose is stopping a design at the wrong place in the
genome — relabeling a coordinate rather than lifting it is the failure the whole
assembly-reconciliation path exists to prevent — so it is the last one that should leave
two of its three audiences without a next step.

The mirror of the round before: there, a check moved *into* the library kept naming a
Python keyword that its new CLI audience could not use. Same rule, read the other way —
a message shared by several surfaces owes each of them something it can act on.
"""

from __future__ import annotations

import re

import pytest

from alleleforge.types.variant import Variant
from alleleforge.variant.resolver import resolve


@pytest.fixture
def mismatch() -> str:
    with pytest.raises(ValueError) as excinfo:
        resolve(
            Variant(chrom="chr1", pos=100, ref="A", alt="T", build="hg19", source_assembly="hg19"),
            build="hg38",
        )
    return str(excinfo.value)


def test_it_still_refuses_rather_than_relabelling(mismatch: str) -> None:
    """The refusal itself is the safety property; the remedy is what was missing."""
    assert "disagrees with requested build" in mismatch
    assert "rather than relabeling" in mismatch


def test_the_command_line_caller_gets_a_command(mismatch: str) -> None:
    assert "aforge lift" in mismatch
    assert "--chain" in mismatch and "--from hg19" in mismatch and "--to hg38" in mismatch


def test_the_python_caller_gets_the_api_that_exists(mismatch: str) -> None:
    from alleleforge.genome.coordinates import Liftover

    assert "Liftover.from_chain_file" in mismatch
    assert hasattr(Liftover, "from_chain_file"), "the message names a constructor that is gone"


def test_the_http_caller_is_told_there_is_no_endpoint(mismatch: str) -> None:
    """Saying "you cannot do this here" is a remedy; silence is not."""
    assert "no lift endpoint" in mismatch
    assert "before sending the request" in mismatch


def test_the_message_says_there_is_no_lift_endpoint_because_there_is_none() -> None:
    """If one is ever added, this claim goes stale and should fail here first."""
    from alleleforge.web.api.app import create_app

    routes = {getattr(route, "path", "") for route in create_app().routes}
    assert not any("lift" in path for path in routes), sorted(p for p in routes if "lift" in p)


def test_the_named_build_values_come_from_the_actual_mismatch(mismatch: str) -> None:
    """A remedy with placeholder builds would send the caller to the wrong chain file."""
    assert len(re.findall(r"hg19", mismatch)) >= 2
    assert len(re.findall(r"hg38", mismatch)) >= 2
