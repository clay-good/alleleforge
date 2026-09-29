"""A clean Python 3.12 CI install resolved NumPy 2.5.3 and mypy never reached us.

AlleleForge supports Python 3.11, so mypy intentionally checks with
``python_version = "3.11"`` even when the type-check job itself runs on Python 3.12.
NumPy 2.5's stubs use Python 3.12 ``type`` statements; mypy rejected that syntax under
the 3.11 target before checking one AlleleForge file. The runtime remains compatible
with newer NumPy. Only the development environment needs the temporary upper bound.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

_ROOT = Path(__file__).parents[1]


def _config() -> dict[str, object]:
    return tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_mypy_checks_the_oldest_supported_python() -> None:
    tool = _config()["tool"]
    assert isinstance(tool, dict)
    mypy = tool["mypy"]
    assert isinstance(mypy, dict)
    assert mypy["python_version"] == "3.11"


def test_the_development_resolver_avoids_python312_only_numpy_stubs() -> None:
    project = _config()["project"]
    assert isinstance(project, dict)
    extras = project["optional-dependencies"]
    assert isinstance(extras, dict)
    assert "numpy<2.5" in extras["dev"]


def test_the_tooling_limit_does_not_constrain_runtime_users() -> None:
    project = _config()["project"]
    assert isinstance(project, dict)
    extras = project["optional-dependencies"]
    assert isinstance(extras, dict)
    assert "numpy>=1.26" in extras["core"]
    assert all("numpy<" not in requirement for requirement in extras["core"])
