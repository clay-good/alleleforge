"""A browser user could not tell a population-aware deployment from a blind one.

The served UI has a Populations box. Whether anything can be done with what a user types
there depends on operator configuration they cannot see or supply, and the status line
reported one bit: `reference loaded` or `no reference configured`.

Until recently that was moot — no population source could reach the web shell at all, and
`app.js` said so in a comment: "`offtarget_sources` is `{}` ... which over HTTP is always,
since no file-backed source can be supplied to this deployment". That is no longer true,
and the comment was the last place still asserting it.

`/api/health` already carries `gnomad_loaded`, `haplotypes_loaded`, `chromatin_tracks` and
`source_errors`. The status line now reports them, including the distinction between a
deployment that configured nothing and one whose configured source could not be read.
"""

from __future__ import annotations

from pathlib import Path

_APP_JS = (
    Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend" / "app.js"
).read_text(encoding="utf-8")


def test_the_status_line_reads_every_health_field() -> None:
    """A field a client cannot supply is one the client must be able to see."""
    for field in ("gnomad_loaded", "haplotypes_loaded", "chromatin_tracks", "source_errors"):
        assert field in _APP_JS, f"the UI ignores /api/health's {field}"


def test_a_deployment_with_no_sources_is_named_as_such() -> None:
    assert "reference-only" in _APP_JS


def test_a_broken_source_is_reported_separately() -> None:
    """A broken mount and a deliberate absence are different facts about a deployment."""
    assert "configured but unreadable" in _APP_JS


def test_the_stale_claim_is_gone() -> None:
    """The comment asserting the web shell can never be population-aware."""
    assert "which over HTTP is always" not in _APP_JS
