"""`pip install alleleforge` shipped an `aforge` that could not start.

The base install is documented — *"Core library (light: pydantic types, config,
model-card parsing — no torch/numpy)"* — and it installs the `aforge` console script,
because the script is declared unconditionally while `typer` lives in the `cli` extra. So
the first thing a user of the documented core install saw was::

    ModuleNotFoundError: No module named 'typer'

`main._missing_dependency` exists for exactly this, and its docstring says so: it gives an
actionable answer *"for the imports that fail before any check runs"*. It could not help,
because it lives inside the module that cannot load. **The one dependency the command is
written in was the one its own remedy could not reach.**

Found by building the conda recipe's expectations by hand. `conda/meta.yaml` declares the
same entry point and its own `test:` block runs `aforge --version`, with a `run:` list of
python, pydantic, pydantic-settings and pyyaml — so the recipe's self-test would have
failed at build time, the same way, in an artifact nobody has built.

The entry point is now a shim in `alleleforge.cli`. It answers for `typer` only: anything
else failing at import is a real defect, and turning every startup error into an install
hint would hide bugs behind an instruction that does not help.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]


def _pyproject() -> dict[str, object]:
    return tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_the_console_script_points_at_the_shim_not_at_the_typer_app() -> None:
    """`alleleforge.cli.main:app` cannot be imported without the `cli` extra."""
    scripts = _pyproject()["project"]["scripts"]  # type: ignore[index]
    assert scripts["aforge"] == "alleleforge.cli:run", (
        "the console script must go through the shim, or a core-only install ships a "
        f"command that dies with a traceback: {scripts['aforge']}"
    )


def test_the_entry_point_name_does_not_collide_with_a_submodule() -> None:
    """`alleleforge.cli.main` is a module, so a shim named `main` is rebound by any
    `import alleleforge.cli.main` in the process — which a test in this file does. The
    console script resolves before that happens, so it was survivable; it is the kind of
    survivable that stops being so the moment an import order changes."""
    import alleleforge.cli as package
    import alleleforge.cli.main  # noqa: F401 — the import that did the rebinding

    name = _pyproject()["project"]["scripts"]["aforge"].split(":")[1]  # type: ignore[index]
    assert callable(getattr(package, name, None)), (
        f"`alleleforge.cli:{name}` is not callable once the submodule is imported — the "
        "entry point collides with a submodule of the same name"
    )


def test_the_shim_does_not_import_typer_at_module_scope() -> None:
    """If it did, it would fail exactly where the command it replaces failed."""
    source = (_ROOT / "src" / "alleleforge" / "cli" / "__init__.py").read_text(encoding="utf-8")
    module_level = [
        line
        for line in source.splitlines()
        if re.match(r"^(import|from)\s", line) and "typer" in line
    ]
    assert not module_level, module_level


def test_the_shim_and_the_dependency_map_name_the_same_extra() -> None:
    """The shim cannot import `main` to read the map, so the two are pinned to agree."""
    from alleleforge.cli import _CLI_EXTRA
    from alleleforge.cli.main import _EXTRA_FOR_MODULE

    assert _EXTRA_FOR_MODULE["typer"] == _CLI_EXTRA


def test_the_extra_the_shim_names_is_one_that_provides_typer() -> None:
    from alleleforge.cli import _CLI_EXTRA

    extras = _pyproject()["project"]["optional-dependencies"]  # type: ignore[index]
    assert any(dep.startswith("typer") for dep in extras[_CLI_EXTRA]), extras[_CLI_EXTRA]


def test_the_shim_re_raises_anything_that_is_not_typer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real import defect must keep its traceback rather than become an install hint.

    The shim answers for one module by name. If it answered for any `ImportError`, a
    genuine bug inside `main.py` would reach the user as "pip install alleleforge[cli]",
    which they have already done.
    """
    import builtins

    import alleleforge.cli as shim

    real_import = builtins.__import__

    def explode(name: str, *args: object, **kwargs: object) -> object:
        if name == "alleleforge.cli.main":
            raise ImportError("a real defect", name="some_other_module")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", explode)
    with pytest.raises(ImportError) as caught:
        shim.run()
    assert caught.value.name == "some_other_module"
    assert not isinstance(caught.value, SystemExit)


def test_the_shim_answers_for_typer_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """And the positive case: a missing typer becomes the install line, not a traceback."""
    import builtins

    import alleleforge.cli as shim

    real_import = builtins.__import__

    def explode(name: str, *args: object, **kwargs: object) -> object:
        if name == "alleleforge.cli.main":
            raise ImportError("No module named 'typer'", name="typer")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", explode)
    with pytest.raises(SystemExit) as caught:
        shim.run()
    assert caught.value.code == 69  # EX_UNAVAILABLE, as ExitCode.UNAVAILABLE uses


# --- the conda recipe, which declares the same entry point and tests it -----------


def _recipe() -> str:
    return (_ROOT / "conda" / "meta.yaml").read_text(encoding="utf-8")


def test_the_recipe_can_run_the_command_it_tests() -> None:
    """Its `test:` block runs `aforge --version`; its `run:` list must support that."""
    recipe = _recipe()
    assert "aforge --version" in recipe, "the recipe no longer tests the command"
    run_block = recipe.split("  run:", 1)[1].split("\ntest:", 1)[0]
    assert re.search(r"^\s*-\s*typer\b", run_block, re.M), (
        "the recipe declares the `aforge` entry point and tests `aforge --version`, but "
        "does not require typer — its own test would fail at build with "
        f"ModuleNotFoundError:\n{run_block}"
    )


def test_the_recipe_ships_the_same_entry_point_as_the_wheel() -> None:
    """Two channels, one command: the *target* has to match, not only the name.

    The recipe named `alleleforge.cli.main:app` — the target this shim was written to
    replace, whose whole problem is that importing it without typer dies with a raw
    traceback. It "worked" only because the recipe happens to require typer, so the
    defect the shim exists to prevent was one `run:` edit away from coming back, on the
    channel where a user is least likely to have the extra. `pip install .` in the
    recipe's own build script already installs the wheel's entry point; conda-build then
    generates this one over it, so a mismatch is two different scripts for one command.
    """
    declared = _pyproject()["project"]["scripts"]["aforge"]  # type: ignore[index]
    recipe = _recipe()
    entry_block = recipe.split("  entry_points:", 1)[1].split("\nrequirements:", 1)[0]
    targets = re.findall(r"-\s*aforge\s*=\s*(\S+)", entry_block)
    assert targets, f"the recipe declares no `aforge` entry point:\n{entry_block}"
    assert targets == [declared], (
        f"the recipe points `aforge` at {targets}, the wheel at {declared!r}. One command "
        "installed two ways must run the same code."
    )


def test_the_recipe_runtime_requirements_cover_the_package_dependencies() -> None:
    """A conda `run:` that omits a base dependency is a package that cannot import."""
    recipe = _recipe()
    run_block = recipe.split("  run:", 1)[1].split("\ntest:", 1)[0]
    required = {
        re.split(r"[><=\s]", dep.strip())[0].replace("_", "-").lower()
        for dep in _pyproject()["project"]["dependencies"]  # type: ignore[index]
    }
    listed = {
        re.split(r"[><=\s]", line.strip().lstrip("- "))[0].replace("_", "-").lower()
        for line in run_block.splitlines()
        if line.strip().startswith("- ")
    }
    missing = sorted(required - listed)
    assert not missing, f"the recipe's run: omits base dependencies: {missing}"
