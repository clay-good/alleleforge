"""The Docker image's install line could not have succeeded.

The image is built only on a `v*` tag — "inert until v0.1.0 is tagged" — and it runs

    RUN pip install ".[core,variant,cli,web,genome-light]"

on `python:3.12-slim`. `variant` is `hgvs>=1.5`; `hgvs` requires `psycopg2`
unconditionally; and psycopg2 publishes **Windows wheels only** (checked against PyPI:
2.9.12 ships six `win_amd64` wheels and an sdist, nothing else). So on Linux pip builds
it from source, which needs `libpq-dev` and a compiler, and `slim` has neither. Run
locally, the exact line fails with `ERROR: Failed to build 'psycopg2'`.

Nothing would have caught it: the docker job runs on a release tag, so the first person
to see it would have been whoever cut the first release.

`variant` was buying the image nothing it could use. `hgvs` is the projector for `c.`/`p.`
HGVS input, which is recorded as *not exposed on the web* in
`test_shells_expose_the_library._NOT_IN_WEB` — "resolved server-side from the request's
variant string". Coordinates, bare contigs and genomic `g.` need no projector; verified
against a venv built from the image's new extras, `/api/resolve`, `/api/design` and
`/api/offtarget` all answer 200, and a `c.` request still returns the refusal that names
the missing library. The alternative — `libpq-dev` in the builder — carries a Postgres
client into an image that never speaks to Postgres.

This file pins the two halves that keep it fixed: the image installs only extras
`pyproject.toml` defines, and it does not install one whose capability the web API is
recorded as unable to reach.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_DOCKERFILE = (_ROOT / "Dockerfile").read_text(encoding="utf-8")


def _image_extras() -> list[str]:
    """Return the extras the image's `pip install` line asks for."""
    match = re.search(r'RUN pip install "\.\[([^\]]+)\]"', _DOCKERFILE)
    assert match, "the Dockerfile no longer installs the project with extras"
    return [e.strip() for e in match.group(1).split(",")]


def _declared_extras() -> dict[str, list[str]]:
    config = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extras: dict[str, list[str]] = config["project"]["optional-dependencies"]
    return extras


def test_there_is_something_to_check() -> None:
    assert len(_image_extras()) >= 3, _image_extras()


def test_every_extra_the_image_installs_exists() -> None:
    """A typo here is a build failure a release tag discovers."""
    unknown = sorted(set(_image_extras()) - set(_declared_extras()))
    assert not unknown, f"the Dockerfile installs extras pyproject does not define: {unknown}"


def test_the_image_does_not_install_the_hgvs_projector() -> None:
    """`hgvs` drags in psycopg2, which has no Linux wheel — and the API cannot use it.

    Named rather than derived from a wheel index on purpose: this must fail offline and
    on the commit that reintroduces it, not only when PyPI is reachable.
    """
    assert "variant" not in _image_extras(), (
        "the image installs `variant`, whose `hgvs` requires psycopg2 — Windows wheels "
        "only, so `python:3.12-slim` builds it from source and the image build fails. "
        "The API cannot reach c./p. HGVS anyway (see _NOT_IN_WEB in "
        "tests/test_shells_expose_the_library.py)."
    )


def test_the_reason_still_holds_that_the_web_cannot_reach_hgvs() -> None:
    """If the web API ever exposes `hgvs`, the trade above needs re-deciding rather than
    silently standing."""
    from tests.test_shells_expose_the_library import _NOT_IN_WEB

    assert "hgvs" in _NOT_IN_WEB, (
        "the web API now exposes `hgvs`, so the image excluding `variant` is no longer "
        "free — revisit the Dockerfile, and the psycopg2 build it implies."
    )


def test_the_image_still_installs_what_the_api_needs() -> None:
    """The web stack and the FASTA reader are what the container is for."""
    extras = set(_image_extras())
    for required in ("web", "genome-light"):
        assert required in extras, f"the image no longer installs `{required}`"


@pytest.mark.parametrize("extra", ["web", "genome-light"])
def test_the_required_extras_declare_real_dependencies(extra: str) -> None:
    assert _declared_extras()[extra], f"{extra} declares no dependencies"
