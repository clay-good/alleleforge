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
#:
#: `specs/` and `openspec/specs/` were not here, and they are the two directories whose
#: stated job is describing the software *as it is now*. The omission cost exactly what
#: it sounds like: `specs/readiness-assessment.md` — the file written so the honest state
#: is not lost across sessions — told a deployer to set `ALLELEFORGE_GNOMAD`, which
#: nothing reads, so following it leaves a silently reference-only deployment. That is
#: the same shape as the guard that once read every surface except the canonical one.
_DOCS = (
    [_ROOT / "README.md", _ROOT / "SPEC.md", _ROOT / "SPEC_V2.md", _ROOT / "CONTRIBUTING.md"]
    + sorted((_ROOT / "docs").rglob("*.md"))
    + sorted((_ROOT / "specs").glob("*.md"))
    + sorted((_ROOT / "openspec" / "specs").rglob("*.md"))
)
#: Any environment variable name a document might list. It was `ALLELEFORGE_`-only,
#: which was fine while the guard only ran documented -> read; checking the reverse
#: direction compares against every name the code reads, and the code also honours
#: the XDG base-directory variables.
_VAR = re.compile(r"(?:ALLELEFORGE|XDG)_[A-Z0-9_]+")
#: A literal variable name handed to `os.environ`, however it is indexed.
_OS_ENVIRON = re.compile(r"os\.environ(?:\.get|\.setdefault)?[\[(]\s*\"([A-Z0-9_]+)\"")


def _honored() -> set[str]:
    """Return every `ALLELEFORGE_*` variable the software actually consults."""
    prefix = str(Settings.model_config.get("env_prefix", ""))
    names = {f"{prefix}{field}".upper() for field in Settings.model_fields}
    for path in (_ROOT / "src").rglob("*.py"):
        names |= set(_OS_ENVIRON.findall(path.read_text()))
    # The root conftest gates the opt-in test markers on their own variables. A
    # contributor sets `ALLELEFORGE_REAL_WEIGHTS` exactly as a deployer sets the others,
    # and it is documented — so scanning `src/` alone would have made a real, honoured,
    # documented variable look like a stray name the moment the doc scan reached the
    # file listing it. Read from the mapping rather than by regex: conftest indexes
    # `os.environ` with a *variable*, so no literal is there to match.
    import conftest

    names |= set(conftest._OPT_IN_MARKERS.values())
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


#: Variables the code reads that no document needs to list, each with the reason. Empty
#: today: every knob an operator can turn is worth writing down.
_UNDOCUMENTED_ON_PURPOSE: dict[str, str] = {}


def test_every_variable_the_code_reads_is_documented() -> None:
    """The direction the guard was missing.

    "Documented but unread" was checked; "read but undocumented" was not, and it failed:
    `ALLELEFORGE_LINDEL_REPO` and `ALLELEFORGE_BEDICT_REPO` are how the *trained* models
    are enabled, named in the CLI's refusal when `--trained-*` is passed without them,
    and listed in no table a reader could consult. A setting nobody can find is a
    capability nobody can turn on.
    """
    documented = set(_documented())
    missing = sorted(_honored() - documented - set(_UNDOCUMENTED_ON_PURPOSE))
    assert not missing, (
        f"the code reads {missing} and no document lists them; an undocumented setting "
        "is one nobody can use"
    )


def test_the_undocumented_allowances_are_real() -> None:
    """A staleness guard on the seam, so it cannot excuse variables nothing reads."""
    unknown = sorted(set(_UNDOCUMENTED_ON_PURPOSE) - _honored())
    assert not unknown, f"allowances for variables the code does not read: {unknown}"


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
