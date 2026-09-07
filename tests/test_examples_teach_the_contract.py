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


def _prints_a_resolved_variant(path: Path) -> bool:
    """Return whether the notebook prints a `Variant` back to its reader."""
    return "resolved.variant" in _code(path)


def test_at_least_one_notebook_prints_a_variant() -> None:
    """Otherwise the rule below is vacuous."""
    assert any(_prints_a_resolved_variant(p) for p in _EXAMPLES)


@pytest.mark.parametrize("path", _EXAMPLES, ids=lambda p: p.name)
def test_a_notebook_that_prints_a_variant_states_the_convention(path: Path) -> None:
    """The trap the renders were taught to warn about, in the file people copy.

    A variant string is read as a **1-based** VCF record and a `Variant` prints its
    position **0-based**, so the value a notebook shows is one lower than the string the
    cell above constructed. Both notebooks that do this had the conversion encoded
    correctly and unexplained — `chr2:71` for offset 70 in one, a bare `EDIT_POS + 1` in
    the other — and then printed the lower number with nothing said. A reader who copies
    the printed variant designs one base away, which is the failure `aforge resolve`
    now names in its refusal and both renders now carry a note about.

    Checked on the whole notebook, code and prose: the note belongs wherever a reader
    meets the number, and markdown is where they will actually read it.
    """
    if not _prints_a_resolved_variant(path):
        return
    text = _text(path).lower()
    assert "1-based" in text and "0-based" in text, path.name
    assert "add 1" in text, f"{path.name}: says the conventions differ, not what to do"


def _text(path: Path) -> str:
    """Return every source line in the notebook, code and markdown alike."""
    notebook = json.loads(path.read_text())
    return "\n".join("".join(cell["source"]) for cell in notebook["cells"])
