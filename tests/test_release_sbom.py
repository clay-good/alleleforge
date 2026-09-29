"""The release SBOM describes the published wheel, not the build environment."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from scripts import build_sbom

ROOT = Path(__file__).resolve().parents[1]


def _wheel(path: Path, *, name: str = "alleleforge", version: str = "1.2.3") -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            f"{name}-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n",
        )
    return path


def _document(*, name: str = "alleleforge", version: str = "1.2.3") -> dict[str, object]:
    return {
        "bomFormat": "CycloneDX",
        "metadata": {
            "component": {
                "bom-ref": f"pkg:pypi/{name}@{version}",
                "name": name,
                "type": "library",
                "version": version,
            }
        },
        "components": [{"name": "pydantic", "version": "2.12.5"}],
        "dependencies": [
            {
                "ref": f"pkg:pypi/{name}@{version}",
                "dependsOn": ["pkg:pypi/pydantic@2.12.5"],
            }
        ],
    }


def test_the_wheel_is_the_authority_for_the_sbom_identity(tmp_path: Path) -> None:
    wheel = _wheel(tmp_path / "not-the-authority-9.9.9.whl")
    assert build_sbom.wheel_identity(wheel) == ("alleleforge", "1.2.3")


def test_the_dynamic_project_version_is_made_explicit_for_cyclonedx() -> None:
    with build_sbom.static_project_metadata("1.2.3") as project:
        rendered = project.read_text(encoding="utf-8")
        assert 'version = "1.2.3"' in rendered
        assert 'dynamic = ["version"]' not in rendered
        assert project.parent == ROOT
    assert not project.exists()


def test_the_sbom_requires_the_wheel_identity_and_an_isolated_runtime() -> None:
    assert build_sbom.validate_sbom(_document(), name="alleleforge", version="1.2.3") == 1

    wrong_version = _document(version="9.9.9")
    with pytest.raises(build_sbom.SbomError, match="does not match the wheel"):
        build_sbom.validate_sbom(wrong_version, name="alleleforge", version="1.2.3")

    contaminated = _document()
    components = contaminated["components"]
    assert isinstance(components, list)
    components.append({"name": "CycloneDX_BOM", "version": "7.4.0"})
    with pytest.raises(build_sbom.SbomError, match="build tooling: cyclonedx-bom"):
        build_sbom.validate_sbom(contaminated, name="alleleforge", version="1.2.3")


def test_ci_and_release_exercise_the_wheel_aware_sbom_builder() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert "python scripts/build_sbom.py" in makefile
    assert "python scripts/build_sbom.py" in ci
    command = "python scripts/build_sbom.py dist/*.whl --output alleleforge.cdx.json"
    assert command in release
    assert release.index("name: dist", release.index("  sbom:")) < release.index(command)
    assert 'pip install -e ".[core,genome,cli,web,ml]"' not in release


def test_a_serialized_valid_document_retains_the_required_graph() -> None:
    """Keep the fixture shaped like the JSON the external generator returns."""
    document = json.loads(json.dumps(_document()))
    assert build_sbom.validate_sbom(document, name="alleleforge", version="1.2.3") == 1
