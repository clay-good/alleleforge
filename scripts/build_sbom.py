"""Build a CycloneDX SBOM for the exact AlleleForge wheel being released."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import venv
import zipfile
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from email.parser import Parser
from pathlib import Path
from typing import Any

if __package__:
    from .check_distribution import DistributionError, build_and_audit
else:
    from check_distribution import DistributionError, build_and_audit

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "pyproject.toml"
_DYNAMIC_VERSION = re.compile(r'^dynamic\s*=\s*\[\s*["\']version["\']\s*\]\s*$', re.MULTILINE)
_FORBIDDEN_COMPONENTS = {"cyclonedx-bom", "cyclonedx-python-lib", "pip", "setuptools"}


class SbomError(RuntimeError):
    """The generated SBOM does not describe the release artifact faithfully."""


def _canonical_name(name: object) -> str:
    return re.sub(r"[-_.]+", "-", str(name)).lower()


def wheel_identity(wheel: Path) -> tuple[str, str]:
    """Read the normalized project name and version from a wheel's own metadata."""
    with zipfile.ZipFile(wheel) as archive:
        metadata_files = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_files) != 1:
            raise SbomError(
                f"expected one .dist-info/METADATA file in {wheel}, found {len(metadata_files)}"
            )
        metadata = Parser().parsestr(archive.read(metadata_files[0]).decode("utf-8"))

    name = metadata.get("Name")
    version = metadata.get("Version")
    if not name or not version:
        raise SbomError(f"wheel metadata has no project name or version: {wheel}")
    return name, version


@contextmanager
def static_project_metadata(version: str) -> Iterator[Path]:
    """Yield a temporary project file whose dynamic wheel version is explicit."""
    project = PROJECT.read_text(encoding="utf-8")
    replacement = f"version = {json.dumps(version)}"
    rendered, count = _DYNAMIC_VERSION.subn(replacement, project)
    if count != 1:
        raise SbomError("pyproject.toml must declare exactly one dynamic version")

    handle, raw_path = tempfile.mkstemp(prefix=".alleleforge-sbom-", suffix=".toml", dir=ROOT)
    path = Path(raw_path)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(rendered)
        yield path
    finally:
        path.unlink(missing_ok=True)


def validate_sbom(document: Mapping[str, Any], *, name: str, version: str) -> int:
    """Check the release identity and isolation properties the generator cannot infer."""
    if document.get("bomFormat") != "CycloneDX":
        raise SbomError("SBOM is not a CycloneDX document")
    metadata = document.get("metadata")
    root = metadata.get("component") if isinstance(metadata, dict) else None
    if not isinstance(root, dict):
        raise SbomError("SBOM has no root component")
    actual_identity = (root.get("name"), root.get("version"), root.get("type"))
    if actual_identity != (name, version, "library"):
        raise SbomError(
            "SBOM root component does not match the wheel: "
            f"expected {(name, version, 'library')}, found {actual_identity}"
        )

    components = document.get("components")
    if not isinstance(components, list) or not components:
        raise SbomError("SBOM contains no runtime dependency components")
    component_names = {
        _canonical_name(component.get("name"))
        for component in components
        if isinstance(component, dict)
    }
    contamination = sorted(_FORBIDDEN_COMPONENTS & component_names)
    if contamination:
        raise SbomError(f"SBOM contains build tooling: {', '.join(contamination)}")

    root_ref = root.get("bom-ref")
    dependencies = document.get("dependencies")
    root_edges = [
        dependency
        for dependency in dependencies or []
        if isinstance(dependency, dict) and dependency.get("ref") == root_ref
    ]
    if not root_ref or len(root_edges) != 1 or not root_edges[0].get("dependsOn"):
        raise SbomError("SBOM has no dependency edge from the AlleleForge root component")
    return len(components)


def _target_python(environment: Path) -> Path:
    return environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def build_sbom(wheel: Path, output: Path) -> int:
    """Install *wheel* in an isolated environment and inventory its runtime closure."""
    wheel = wheel.resolve()
    output = output.resolve()
    if not wheel.is_file():
        raise SbomError(f"wheel not found: {wheel}")
    name, version = wheel_identity(wheel)
    if name != "alleleforge":
        raise SbomError(f"expected an alleleforge wheel, found {name!r}")

    with tempfile.TemporaryDirectory(prefix="alleleforge-sbom-env-") as directory:
        environment = Path(directory)
        venv.EnvBuilder(with_pip=False).create(environment)
        python = _target_python(environment)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "--python",
                str(python),
                "install",
                "--disable-pip-version-check",
                str(wheel),
            ],
            cwd=ROOT,
            check=True,
        )
        with static_project_metadata(version) as project:
            clean_environment = os.environ.copy()
            clean_environment.pop("PYTHONPATH", None)
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "cyclonedx_py",
                    "environment",
                    "--pyproject",
                    str(project),
                    "--mc-type",
                    "library",
                    "--output-reproducible",
                    "--of",
                    "JSON",
                    "-o",
                    str(output),
                    str(python),
                ],
                cwd=ROOT,
                env=clean_environment,
                check=True,
            )

    document = json.loads(output.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise SbomError("CycloneDX output is not a JSON object")
    return validate_sbom(document, name=name, version=version)


def _run(wheel: Path | None, output: Path) -> int:
    if wheel is not None:
        return build_sbom(wheel, output)
    with tempfile.TemporaryDirectory(prefix="alleleforge-sbom-dist-") as directory:
        built_wheel, _ = build_and_audit(Path(directory))
        return build_sbom(built_wheel, output)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", nargs="?", type=Path, help="validated wheel to inventory")
    parser.add_argument("--output", type=Path, help="keep the validated SBOM at this path")
    args = parser.parse_args(argv)
    try:
        if args.output is not None:
            output = args.output
            count = _run(args.wheel, output)
            result = str(output.resolve())
        else:
            with tempfile.TemporaryDirectory(prefix="alleleforge-sbom-output-") as directory:
                output = Path(directory) / "alleleforge.cdx.json"
                count = _run(args.wheel, output)
            result = "temporary output"
    except (
        DistributionError,
        SbomError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
        zipfile.BadZipFile,
    ) as exc:
        print(f"SBOM build failed: {exc}", file=sys.stderr)
        return 1
    print(f"SBOM audit passed: {result} ({count} runtime components)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
