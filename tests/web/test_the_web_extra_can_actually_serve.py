"""`pip install "alleleforge[web]"` must be able to run the documented command.

`docs/api/web.md` and the README both say:

    pip install "alleleforge[web]"
    export ALLELEFORGE_REFERENCE_FASTA=/path/to/hg38.fa
    uvicorn alleleforge.web.api.app:app --port 8000

The `web` extra was `fastapi`, `uvicorn`, `httpx` — no FASTA reader. So the third line
died at import with `ModuleNotFoundError: No module named 'pyfaidx'`, because
`app = create_app()` runs at module scope and reads that environment variable.

The Dockerfile already knew: it installs `".[core,variant,cli,web]"` **plus**
`"pyfaidx>=0.8"`, with a comment explaining that the API needs only the light FASTA
reader and not the heavy pysam/cyvcf2/mappy chain. That reasoning is right and it
belongs in the extra, so the documented one-liner works and the image stops
compensating for it.

The second half is defence. A previous round made an unreadable reference fail
gracefully — the service starts and answers `503` with the reason — but it caught
`OSError`, and a missing dependency raises `ImportError`. The graceful path has to
cover both, because "the operator's environment is not what the app needs" is one
situation with two exception types, and a container that will not start is the worst
possible way to report either.
"""

from __future__ import annotations

import builtins
import tomllib
from collections.abc import Iterator
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def test_the_web_extra_includes_a_fasta_reader() -> None:
    """The documented install must be able to open the reference it is given."""
    pyproject = tomllib.loads((_ROOT / "pyproject.toml").read_text())
    web = pyproject["project"]["optional-dependencies"]["web"]
    assert any(dep.startswith("pyfaidx") for dep in web), (
        f"`pip install 'alleleforge[web]'` installs {web}, none of which can read a "
        "FASTA — so the documented `uvicorn alleleforge.web.api.app:app` dies at "
        "import as soon as ALLELEFORGE_REFERENCE_FASTA is set."
    )


def test_the_dockerfile_no_longer_compensates() -> None:
    """The image added pyfaidx by hand because the extra lacked it; that is drift."""
    dockerfile = (_ROOT / "Dockerfile").read_text()
    install = next(line for line in dockerfile.splitlines() if line.startswith("RUN pip install"))
    assert "[core,variant,cli,web]" in install
    assert '"pyfaidx' not in install, install


@pytest.fixture
def without_pyfaidx(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Raise on the pyfaidx import the way a `[web]`-without-reader install does.

    Raised inside `builtins.__import__` rather than by evicting `sys.modules`, which
    re-imports `alleleforge` and resets its singletons.
    """
    real_import = builtins.__import__

    def blocked(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith(("pyfaidx", "alleleforge.genome.reference")):
            raise ModuleNotFoundError("No module named 'pyfaidx'", name="pyfaidx")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", blocked)
    yield


def test_the_app_starts_and_records_why_it_has_no_reference(
    without_pyfaidx: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A container that will not boot is the worst way to report a bad environment.

    Scoped to booting and to `/api/health`, deliberately. With no FASTA reader the
    *design* stack cannot import either, so a `/api/design` request in this state
    fails on its own imports rather than reaching the 503 — that is a real property
    of an install with no genome layer at all, and not what this is about. What the
    catch buys is that `create_app()` returns instead of raising, so an operator gets
    a running service and a recorded reason rather than a traceback in a container
    log.
    """
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import alleleforge.web.api.app as module

    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "AT" * 70 + "\n")
    monkeypatch.setenv("ALLELEFORGE_REFERENCE_FASTA", str(fasta))

    client = TestClient(module.create_app())
    assert client.get("/api/health").json()["reference_loaded"] is False
    assert "pyfaidx" in (module._REFERENCE_LOAD_ERROR or "")
