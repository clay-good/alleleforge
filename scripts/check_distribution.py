"""Build and audit the exact Python distributions a release would publish."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SOURCE = ROOT / "src" / "alleleforge"


class DistributionError(RuntimeError):
    """A built distribution does not satisfy the release contract."""


def _runtime_resources(root: Path) -> set[str]:
    """Return non-Python files that runtime code may load from the package."""
    return {
        path.relative_to(root.parent).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.suffix not in {".py", ".pyc"} and "__pycache__" not in path.parts
    }


def _wheel_resources(wheel: Path) -> set[str]:
    """Return runtime resources carried by *wheel*."""
    with zipfile.ZipFile(wheel) as archive:
        return {
            name
            for name in archive.namelist()
            if name.startswith("alleleforge/")
            and not name.endswith("/")
            and Path(name).suffix not in {".py", ".pyc"}
            and "__pycache__" not in Path(name).parts
        }


def audit_wheel_resources(wheel: Path, source: Path = PACKAGE_SOURCE) -> None:
    """Require the wheel and source tree to carry the same runtime resources."""
    expected = _runtime_resources(source)
    actual = _wheel_resources(wheel)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing or unexpected:
        details = []
        if missing:
            details.append(f"missing from wheel: {', '.join(missing)}")
        if unexpected:
            details.append(f"present only in wheel: {', '.join(unexpected)}")
        raise DistributionError("; ".join(details))


def _build_and_audit(output: Path) -> tuple[Path, Path]:
    if output.exists() and any(output.iterdir()):
        raise DistributionError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(output)],
        cwd=ROOT,
        check=True,
    )
    wheels = sorted(output.glob("*.whl"))
    sdists = sorted(output.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise DistributionError(
            f"expected one wheel and one sdist, found {len(wheels)} wheel(s) "
            f"and {len(sdists)} sdist(s)"
        )

    subprocess.run(
        [sys.executable, "-m", "twine", "check", str(wheels[0]), str(sdists[0])],
        cwd=ROOT,
        check=True,
    )
    audit_wheel_resources(wheels[0])
    return wheels[0], sdists[0]


def main(argv: Sequence[str] | None = None) -> int:
    """Build in a clean directory, validate metadata, and audit packaged resources."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--outdir",
        type=Path,
        help="keep the validated artifacts here; the directory must be empty",
    )
    args = parser.parse_args(argv)

    try:
        if args.outdir is not None:
            wheel, sdist = _build_and_audit(args.outdir.resolve())
        else:
            with tempfile.TemporaryDirectory(prefix="alleleforge-dist-") as directory:
                wheel, sdist = _build_and_audit(Path(directory))
                print(f"distribution audit passed: {wheel.name}, {sdist.name}")
                return 0
    except (DistributionError, subprocess.CalledProcessError) as exc:
        print(f"distribution audit failed: {exc}", file=sys.stderr)
        return 1

    print(f"distribution audit passed: {wheel}, {sdist}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
