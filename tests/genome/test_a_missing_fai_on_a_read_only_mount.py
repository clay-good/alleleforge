"""A reference whose `.fai` cannot be written must fail with actionable words.

Opening a reference writes `<fasta>.fai` beside it when one is absent — a file the
caller did not name, outside the cache directory, which `SECURITY.md` scopes
explicitly ("write outside the cache directory"). That is pyfaidx's behaviour and it
is fine when the directory is writable.

The shipped `docker-compose.yml` mounts it read-only:

    volumes:
      - ./data:/data:ro          # reference genome (read-only)

and its header says to place the FASTA there "(and its .fai **if present**)". With a
read-only mount the `.fai` is not optional, it is required, and without one the
documented deployment fails three ways:

* `uvicorn alleleforge.web.api.app:app` — the command in the deployment guide and the
  Dockerfile — **dies at import**, because `app = create_app()` runs at module scope.
  Not a 503: a pyfaidx traceback and a container that will not start.
* the CLI relays pyfaidx's own words: *"Please use Fasta(rebuild=False),
  Faidx(rebuild=False) or faidx --no-rebuild"* — advice about a Python API the user is
  not calling, and which `ReferenceGenome` already passes.
* nothing anywhere names the actual remedy, which is one `samtools faidx` away.

The message is the fix. The situation is legitimate — a read-only reference mount is
good practice, and this project recommends it — so the tool must explain it rather
than refuse in someone else's vocabulary.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from alleleforge.errors import ReferenceIndexError
from alleleforge.genome.reference import ReferenceGenome


@pytest.fixture
def read_only_fasta(tmp_path: Path) -> Path:
    """A FASTA with no `.fai`, in a directory nothing may write to."""
    directory = tmp_path / "data"
    directory.mkdir()
    fasta = directory / "reference.fa"
    fasta.write_text(">chr2\n" + "AT" * 70 + "\n")
    directory.chmod(stat.S_IRUSR | stat.S_IXUSR)
    yield fasta
    directory.chmod(stat.S_IRWXU)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores the write bit")
def test_the_error_names_the_file_and_the_remedy(read_only_fasta: Path) -> None:
    with pytest.raises(ReferenceIndexError) as excinfo:
        ReferenceGenome(read_only_fasta)
    message = str(excinfo.value)
    assert "reference.fa.fai" in message
    assert "samtools faidx" in message
    assert "read-only" in message or "not writable" in message


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores the write bit")
def test_it_does_not_relay_pyfaidx_internals(read_only_fasta: Path) -> None:
    """`Fasta(rebuild=False)` is advice about an API the caller is not using."""
    with pytest.raises(ReferenceIndexError) as excinfo:
        ReferenceGenome(read_only_fasta)
    assert "rebuild=False" not in str(excinfo.value)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores the write bit")
def test_an_existing_fai_opens_fine(read_only_fasta: Path) -> None:
    """The remedy has to actually work: with an index present, read-only is fine."""
    directory = read_only_fasta.parent
    directory.chmod(stat.S_IRWXU)
    ReferenceGenome(read_only_fasta)  # writes the .fai
    directory.chmod(stat.S_IRUSR | stat.S_IXUSR)

    genome = ReferenceGenome(read_only_fasta)
    assert genome.contigs == ("chr2",)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores the write bit")
def test_the_web_app_starts_and_reports_503(read_only_fasta: Path, monkeypatch) -> None:
    """A container that will not start is worse than one that says it has no genome.

    `create_app()` runs at module scope, so an unreadable reference took the whole
    process down at import rather than leaving the documented "no reference
    configured" path to answer.
    """
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from alleleforge.web.api.app import create_app

    monkeypatch.setenv("ALLELEFORGE_REFERENCE_FASTA", str(read_only_fasta))
    client = TestClient(create_app())
    assert client.get("/api/health").json()["reference_loaded"] is False
    response = client.post("/api/design", json={"variant": "chr2:71:A>C"})
    assert response.status_code == 503
    assert "samtools faidx" in response.text
