"""The release artifacts are checked before any workflow can publish them."""

from __future__ import annotations

import importlib.util
import tomllib
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _checker() -> ModuleType:
    path = ROOT / "scripts" / "check_distribution.py"
    spec = importlib.util.spec_from_file_location("check_distribution", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_wheel_must_carry_every_runtime_resource(tmp_path: Path) -> None:
    checker = _checker()
    source = tmp_path / "src" / "alleleforge"
    source.mkdir(parents=True)
    (source / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (source / "model.json").write_text("{}\n", encoding="utf-8")
    wheel = tmp_path / "package.whl"

    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("alleleforge/module.py", "VALUE = 1\n")

    with pytest.raises(checker.DistributionError, match="alleleforge/model.json"):
        checker.audit_wheel_resources(wheel, source)

    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr("alleleforge/model.json", "{}\n")
    checker.audit_wheel_resources(wheel, source)


def test_ci_and_release_run_the_same_distribution_audit() -> None:
    command = "python scripts/check_distribution.py"
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert command in makefile
    assert command in ci
    assert f"{command} --outdir dist" in release
    assert release.index(f"{command} --outdir dist") < release.index("gh-action-pypi-publish")


def test_the_development_toolchain_excludes_the_known_broken_twine() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev = project["project"]["optional-dependencies"]["dev"]
    assert "build>=1.2" in dev
    assert "twine>=7.0" in dev
