"""Nothing said whether the native kernels were in play, and that is the point of them.

The Rust kernels are held to a parity suite proving they return exactly what the Python
implementation returns. That is the right requirement and it makes them invisible: an
install without the extension — or with a **stale** one, older than the crate source it
sits beside — produces identical output, an order of magnitude slower on the off-target
hot path, and no surface said which install you had.

`aforge --version` printed one line. `GET /api/health` reports which optional data sources
a deployment loaded and which scan-reuse stores it enabled, for exactly this reason ("a
client has no other way to learn that two deployments running the same code answer at very
different speeds") — and said nothing about the code itself.

The stale case is not only about speed. The kernel it hides is the off-target evaluation
hot path, whose entire safety argument is that parity suite, and those tests *skip
themselves* when the kernel is absent: a stale extension silently falls back to Python and
takes its own verification with it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from alleleforge import _native
from alleleforge._native import acceleration
from alleleforge._version import __version__
from alleleforge.cli.main import app
from alleleforge.web.api.app import create_app


def test_the_line_names_the_build_when_one_is_installed() -> None:
    line = acceleration()
    assert line.startswith("native kernels: ")
    if _native.NATIVE_AVAILABLE and not _native.missing_native_functions():
        assert _native.native_version() in line
        assert "not installed" not in line and "STALE" not in line


def test_a_missing_extension_says_so_and_says_what_it_costs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_native, "native_version", lambda: None)
    line = acceleration()
    assert "not installed" in line
    # Results are identical — the reason this was invisible — and that has to be said,
    # or a reader takes "not installed" for "degraded output".
    assert "identical" in line and "slower" in line


def test_a_stale_extension_is_reported_as_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    """The dangerous one: the kernel falls back *and* its parity tests skip themselves."""
    monkeypatch.setattr(_native, "native_version", lambda: "9.9.9")
    monkeypatch.setattr(_native, "missing_native_functions", lambda: frozenset({"cfd_eval"}))
    line = acceleration()
    assert "STALE" in line and "cfd_eval" in line
    assert "Rebuild" in line


def test_the_command_line_reports_it_under_version() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert lines[0] == __version__, "the version must stay alone on the first line"
    assert lines[1] == acceleration()


def test_the_health_report_carries_the_same_sentence() -> None:
    """One wording, three surfaces: the library's, not each shell's."""
    with TestClient(create_app(reference=None)) as client:
        payload = client.get("/api/health").json()
    assert payload["native_kernels"] == acceleration()
