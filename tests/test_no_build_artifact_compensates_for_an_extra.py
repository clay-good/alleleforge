"""A build artifact must not install by hand what an extra should provide.

`pip install "alleleforge[web]"` used to be broken because the extra had no FASTA
reader — and the Dockerfile compensated, adding `"pyfaidx>=0.8"` on top of it with a
comment explaining why. So the documented install worked in exactly one place, and the
knowledge that it was insufficient lived in the image rather than in the package.

Grepping for that pattern found it eleven more times: `"pyfaidx>=0.8"
"pyliftover>=0.4"` appended to an extra in seven CI jobs and the Makefile. Not a bug —
those builds got what they needed — but a real dependency set with no name, assembled
by hand everywhere, which nobody outside the repository could ask for. It is
`genome-light` now, and `genome` is defined in terms of it so the two cannot diverge.

The rule this pins: where a build installs the package, it names extras and nothing
else. A dependency appended there is either missing from an extra (the `[web]` bug) or
a set that deserves a name (this one). Tools that are not the package — `pip-audit`,
`build`, `cyclonedx-bom` — are not dependencies of it and are listed as exempt.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]

#: Installs of *other* tools alongside the package. These are not package dependencies
#: and belong on the command line, not in an extra.
_NOT_PACKAGE_DEPENDENCIES = {"pip-audit", "build", "cyclonedx-bom", "twine"}

#: `pip install …` lines in every artifact that builds or gates this project.
_ARTIFACTS = (
    Path("Makefile"),
    Path("Dockerfile"),
    Path(".github/workflows/ci.yml"),
    Path(".github/workflows/release.yml"),
)

#: A quoted requirement like `"pyfaidx>=0.8"` — the shape a compensation takes.
_QUOTED_REQUIREMENT = re.compile(r'"([A-Za-z][A-Za-z0-9._-]*)(?:[<>=!~][^"]*)?"')


def _install_lines() -> list[tuple[str, str]]:
    """Return `(artifact, line)` for every `pip install` of this package."""
    found: list[tuple[str, str]] = []
    for artifact in _ARTIFACTS:
        path = _ROOT / artifact
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            stripped = line.strip()
            if "pip install" in stripped and not stripped.startswith("#"):
                found.append((str(artifact), stripped))
    return found


def test_there_are_install_lines_to_check() -> None:
    """Guard the guard: a regex that finds nothing would pass every case."""
    lines = _install_lines()
    assert len(lines) >= 8, lines
    assert any("Makefile" in artifact for artifact, _ in lines)


def test_no_install_line_appends_a_package_dependency() -> None:
    """A dependency appended to an extra is a missing extra, or an unnamed set."""
    offenders = []
    for artifact, line in _install_lines():
        # Only lines that install *this* package; `pip install build` is not one.
        if not re.search(r'pip install .*["\'.]?\.?\[|pip install -e "\.', line):
            continue
        for requirement in _QUOTED_REQUIREMENT.findall(line):
            name = requirement.strip()
            if name.startswith(".") or name in _NOT_PACKAGE_DEPENDENCIES:
                continue
            offenders.append(f"{artifact}: {name!r} in `{line}`")
    assert not offenders, (
        "a build installs a dependency alongside an extra: "
        + "; ".join(offenders)
        + ". Either the extra is missing it (so every other install is broken), or "
        "the set deserves a name — see `genome-light`."
    )


def test_genome_light_exists_and_genome_builds_on_it() -> None:
    """The name must be real, and the two must not be able to diverge."""
    extras = tomllib.loads((_ROOT / "pyproject.toml").read_text())["project"][
        "optional-dependencies"
    ]
    assert "genome-light" in extras
    assert any(dep.startswith("pyfaidx") for dep in extras["genome-light"])
    assert any(dep.startswith("pyliftover") for dep in extras["genome-light"])
    assert "alleleforge[genome-light]" in extras["genome"], (
        "`genome` must be defined in terms of `genome-light`, or the light half can "
        "drift out of the full one."
    )


@pytest.mark.parametrize("heavy", ["pysam", "cyvcf2", "mappy"])
def test_the_light_extra_stays_light(heavy: str) -> None:
    """Its whole purpose is excluding the compiled chain; that is worth pinning."""
    extras = tomllib.loads((_ROOT / "pyproject.toml").read_text())["project"][
        "optional-dependencies"
    ]
    assert not any(dep.startswith(heavy) for dep in extras["genome-light"])
    assert any(dep.startswith(heavy) for dep in extras["genome"])
