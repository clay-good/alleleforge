"""Fixtures for the Phase 13 web API tests (require the optional ``web`` extra)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

import httpx  # noqa: E402
from fastapi import FastAPI  # noqa: E402

from alleleforge.genome.reference import ReferenceGenome  # noqa: E402
from alleleforge.web.api.app import create_app  # noqa: E402


def _prime_contig() -> str:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")  # plus pegRNA PAM
    seq[55:58] = list("CCA")  # minus ngRNA PAM (PE3b)
    return "".join(seq)


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    """A small reference whose chr2:71:A>C locus yields prime candidates."""
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + _prime_contig() + "\n")
    return ReferenceGenome(fasta, build="hg38")


@pytest.fixture
def app(reference: ReferenceGenome) -> FastAPI:
    """An app with the reference wired in."""
    return create_app(reference=reference)


@pytest.fixture
def app_no_reference() -> FastAPI:
    """An app with no reference configured (design/offtarget should 503)."""
    return create_app(reference=None)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """An httpx client speaking to the app in-process (no sockets opened)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
