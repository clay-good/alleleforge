"""The performance script must not fall behind the crate it measures.

The round log carries a dozen speedup claims in prose. Prose cannot be re-measured,
so `scripts/native_speedup.py` exists to reproduce them - but for several rounds it
timed four kernels while the crate had grown to six, and nothing said so. A kernel
nobody times is a kernel whose claimed speedup nobody can check, and a regression in
it is invisible.

This pins both directions: every function the crate registers is timed by some
section of the script, and every name the script claims to time is still registered
(so the map cannot rot into a list of kernels that no longer exist).
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_LIB_RS = _ROOT / "rust" / "src" / "lib.rs"
_SCRIPT = _ROOT / "scripts" / "native_speedup.py"

#: Registered but deliberately untimed: `version` reports the crate build, it does no
#: work worth a wall-clock number.
_NOT_A_KERNEL = {"version"}


def _registered() -> set[str]:
    source = _LIB_RS.read_text(encoding="utf-8")
    return set(re.findall(r"wrap_pyfunction!\((\w+),", source))


def _timed() -> dict[str, str]:
    namespace: dict[str, object] = {}
    body = _SCRIPT.read_text(encoding="utf-8")
    table = body[
        body.index("TIMED_KERNELS = {") : body.index("}\n", body.index("TIMED_KERNELS")) + 1
    ]
    exec(table, namespace)  # noqa: S102 - our own literal, not user input
    timed = namespace["TIMED_KERNELS"]
    assert isinstance(timed, dict)
    return timed


def test_every_native_kernel_is_timed_by_the_script() -> None:
    missing = _registered() - _NOT_A_KERNEL - set(_timed())
    assert not missing, (
        f"the crate exposes {sorted(missing)} but scripts/native_speedup.py does not "
        "time them - add a section, or the speedup claim for that kernel is prose only"
    )


def test_the_script_does_not_claim_to_time_a_kernel_that_is_gone() -> None:
    stale = set(_timed()) - _registered()
    assert not stale, f"scripts/native_speedup.py names unregistered kernel(s): {sorted(stale)}"


def test_the_exemptions_are_still_real() -> None:
    """A staleness guard on the guard: an exemption for a function nobody registers."""
    assert _NOT_A_KERNEL <= _registered()


def test_each_named_section_is_actually_printed() -> None:
    """The map is only meaningful if its headings match sections the script prints."""
    body = _SCRIPT.read_text(encoding="utf-8")
    for kernel, heading in _timed().items():
        printed = re.search(rf'print\(f?"(\\n)?{re.escape(heading)}', body)
        assert printed, (
            f"{kernel} claims to be timed under {heading!r}, but the script prints no such section"
        )
