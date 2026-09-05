"""The example notebooks are documentation people copy, so they must teach the rules.

The cohort notebook rendered `best_eff` as a lone rounded float — the same omission
fixed on the CLI, the report and the browser table, in the file a user is most likely
to paste into their own script. It also wrote `s.get("best_efficiency") or float("nan")`,
which turns a genuine efficiency of exactly `0.0` into NaN: the falsy-default shape that
had already produced a shipped bug in this same notebook once before.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_EXAMPLES = sorted((Path(__file__).resolve().parents[1] / "examples").glob("*.ipynb"))


def _code(path: Path) -> str:
    notebook = json.loads(path.read_text())
    return "\n".join(
        "".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"
    )


def test_there_are_notebooks_to_check() -> None:
    assert _EXAMPLES, "no example notebooks found — every check below would be vacuous"


@pytest.mark.parametrize("path", _EXAMPLES, ids=lambda p: p.name)
def test_a_notebook_showing_an_efficiency_shows_its_interval(path: Path) -> None:
    """An example that prints a point estimate alone teaches that this is acceptable."""
    code = _code(path)
    if "best_efficiency" not in code:
        return
    assert "best_efficiency_low" in code and "best_efficiency_high" in code, (
        f"{path.name} renders best_efficiency without its interval"
    )


@pytest.mark.parametrize("path", _EXAMPLES, ids=lambda p: p.name)
def test_a_notebook_does_not_default_a_summary_value_with_or(path: Path) -> None:
    """`x or default` fires on `0.0` and `0`, which are meaningful values here.

    An efficiency of exactly 0.0 and a candidate count of 0 are real answers. This
    notebook has already shipped one bug of this shape (a `.get` default that did not
    fire because the key existed with value `None`), so the pattern is worth pinning.
    """
    code = _code(path)
    for field in ("best_efficiency", "worst_offtarget", "best_specificity"):
        assert f'"{field}") or ' not in code, (
            f"{path.name} defaults {field} with `or`, which also fires on a real 0.0"
        )
