"""An `ALLELEFORGE_*` variable the docs name must be one the software reads.

`docs/deployment.md` tabulated the reference build as `ALLELEFORGE_REFERENCE_BUILD`.
The `Settings` field is `reference`, so the variable the software reads is
`ALLELEFORGE_REFERENCE`, and exporting the documented name did nothing:

    ALLELEFORGE_REFERENCE_BUILD=mm39  ->  Settings().reference == 'hg38'

Silently. A user who sets the reference build and is not told it was ignored designs
against hg38 coordinates believing they are on mm39, which is the same failure mode as
a coordinate-base mixup and just as invisible. The table also omitted
`ALLELEFORGE_ALLOW_NETWORK`, the switch that governs whether the library may reach the
network at all.

The check is mechanical, and it is R210's query one surface over: prose that names an
interface can be validated against the interface. A variable is "read" if it is a
`Settings` field under the `ALLELEFORGE_` prefix, or if `src/` passes its literal name
to `os.environ`. Anything else in the docs is a name that goes nowhere.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from alleleforge.config import Settings

_ROOT = Path(__file__).resolve().parents[1]
#: Prose surfaces a deployer actually reads. `openspec/changes/README.md` is the audit
#: log, which quotes historical mistakes on purpose and is therefore excluded.
_DOCS = [_ROOT / "README.md", _ROOT / "SPEC.md", _ROOT / "SPEC_V2.md"] + sorted(
    (_ROOT / "docs").rglob("*.md")
)
_VAR = re.compile(r"ALLELEFORGE_[A-Z0-9_]+")
#: A literal variable name handed to `os.environ`, however it is indexed.
_OS_ENVIRON = re.compile(r"os\.environ(?:\.get|\.setdefault)?[\[(]\s*\"([A-Z0-9_]+)\"")


def _honored() -> set[str]:
    """Return every `ALLELEFORGE_*` variable the software actually consults."""
    prefix = str(Settings.model_config.get("env_prefix", ""))
    names = {f"{prefix}{field}".upper() for field in Settings.model_fields}
    for path in (_ROOT / "src").rglob("*.py"):
        names |= set(_OS_ENVIRON.findall(path.read_text()))
    return names


def _documented() -> dict[str, list[str]]:
    """Return every `ALLELEFORGE_*` name each doc mentions."""
    found: dict[str, list[str]] = {}
    for path in _DOCS:
        if not path.is_file():
            continue
        for name in sorted(set(_VAR.findall(path.read_text()))):
            found.setdefault(name, []).append(str(path.relative_to(_ROOT)))
    return found


def test_the_scan_is_not_vacuous() -> None:
    """Guard the guard: both sides must actually find names."""
    honored, documented = _honored(), _documented()
    assert "ALLELEFORGE_SEED" in honored and "ALLELEFORGE_REFERENCE" in honored, honored
    assert len(documented) >= 5, documented


def test_every_documented_env_var_is_read() -> None:
    honored = _honored()
    stray = {name: where for name, where in _documented().items() if name not in honored}
    assert not stray, (
        "documented environment variable(s) the software never reads, so setting them "
        f"does nothing and says nothing: {stray}. Honored names: {sorted(honored)}"
    )


@pytest.mark.parametrize(
    "name", ["ALLELEFORGE_SEED", "ALLELEFORGE_REFERENCE", "ALLELEFORGE_ALLOW_NETWORK"]
)
def test_a_setting_really_moves_when_its_variable_is_set(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The honored list is derived, so pin that the derivation matches behaviour."""
    field = name.removeprefix("ALLELEFORGE_").lower()
    before = getattr(Settings(), field)
    monkeypatch.setenv(name, {"seed": "1234", "reference": "mm39", "allow_network": "1"}[field])
    after = getattr(Settings(), field)
    assert after != before, f"{name} did not move Settings().{field}"
