"""The dataset manager can acquire and refresh a pinned release from the shell.

Phase 12 promises that ``aforge data`` manages datasets, including fetch and refresh.
The registry implemented the consent/checksum/atomic-write boundary, but the CLI exposed
only ``list`` and ``show``. A user could be told that ClinVar was fetchable and still had
no command that performed the fetch.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app
from alleleforge.data import registry as data_registry
from alleleforge.data.registry import DatasetDescriptor, DatasetRegistry

_PAYLOAD = b"pinned release\n"
_DIGEST = hashlib.sha256(_PAYLOAD).hexdigest()


def _registry(*, pinned: bool = True) -> DatasetRegistry:
    return DatasetRegistry(
        {
            "demo": DatasetDescriptor(
                name="demo",
                version="1.0",
                source_url="https://example.invalid/demo.tsv",
                license="CC0-1.0",
                citation="Demo et al. 2024",
                sha256=_DIGEST if pinned else None,
                redistributable=True,
                filename="demo.tsv",
            )
        }
    )


def _install_fake_registry(monkeypatch: object, *, pinned: bool = True) -> list[str]:
    calls: list[str] = []

    def download(url: str, dest: Path) -> None:
        calls.append(url)
        dest.write_bytes(_PAYLOAD)

    monkeypatch.setattr(data_registry, "DEFAULT_REGISTRY", _registry(pinned=pinned))  # type: ignore[attr-defined]
    monkeypatch.setattr(data_registry, "_default_downloader", download)  # type: ignore[attr-defined]
    return calls


def test_fetch_downloads_a_pinned_release_to_the_selected_cache(
    runner: CliRunner, monkeypatch: object, tmp_path: Path
) -> None:
    calls = _install_fake_registry(monkeypatch)
    result = runner.invoke(app, ["--cache-dir", str(tmp_path), "data", "fetch", "demo", "--json"])
    assert result.exit_code == 0, result.output + result.stderr
    payload = json.loads(result.stdout)
    path = tmp_path / "data" / "demo" / "demo.tsv"
    assert payload == {
        "name": "demo",
        "version": "1.0",
        "path": str(path),
        "sha256": _DIGEST,
        "refreshed": False,
    }
    assert path.read_bytes() == _PAYLOAD
    assert calls == ["https://example.invalid/demo.tsv"]


def test_fetch_reuses_a_verified_cache_and_refresh_replaces_it(
    runner: CliRunner, monkeypatch: object, tmp_path: Path
) -> None:
    calls = _install_fake_registry(monkeypatch)
    argv = ["--cache-dir", str(tmp_path), "data"]
    first = runner.invoke(app, [*argv, "fetch", "demo"])
    second = runner.invoke(app, [*argv, "fetch", "demo"])
    refreshed = runner.invoke(app, [*argv, "refresh", "demo", "--json"])
    assert first.exit_code == second.exit_code == refreshed.exit_code == 0
    assert len(calls) == 2, "fetch should reuse the cache; refresh should download again"
    assert json.loads(refreshed.stdout)["refreshed"] is True


def test_fetch_refuses_an_unpinned_or_unknown_release(
    runner: CliRunner, monkeypatch: object, tmp_path: Path
) -> None:
    _install_fake_registry(monkeypatch, pinned=False)
    argv = ["--cache-dir", str(tmp_path), "data", "fetch"]
    unpinned = runner.invoke(app, [*argv, "demo"])
    unknown = runner.invoke(app, [*argv, "unknown"])
    assert unpinned.exit_code == ExitCode.UNAVAILABLE
    assert "no pinned checksum" in unpinned.stderr
    assert unknown.exit_code == ExitCode.MISSING_DATA
    assert "unknown dataset" in unknown.stderr


def test_status_is_the_dataset_listing(runner: CliRunner, monkeypatch: object) -> None:
    _install_fake_registry(monkeypatch)
    listed = runner.invoke(app, ["data", "list", "--json"])
    status = runner.invoke(app, ["data", "status", "--json"])
    assert listed.exit_code == status.exit_code == 0
    assert json.loads(status.stdout) == json.loads(listed.stdout)


def test_refresh_does_not_claim_to_replace_a_bundled_artifact(runner: CliRunner) -> None:
    result = runner.invoke(app, ["data", "refresh", "doench-2016-cfd"])
    assert result.exit_code == ExitCode.UNAVAILABLE
    assert "bundled with AlleleForge" in result.stderr
    assert "upgrade the package" in result.stderr
