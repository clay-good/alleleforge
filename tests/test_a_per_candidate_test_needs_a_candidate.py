"""Fourteen tests named `test_every_candidate_...` passed on a menu with no candidates.

Their whole body was `for c in <candidates>: assert ...`. An empty list runs the loop
zero times and the test is green, so each one asserted the per-candidate contract only
while something else happened to produce candidates.

That is not a hypothetical failure mode here. This project has shipped an empty menu — a
large precise edit produced no candidates at all until the nuclease+HDR route was added —
and these are precisely the tests whose *names* claim to guard the per-candidate contract.
Mutating all three design verticals to `return []` broke 149 tests across the suite and
left every one of these fourteen green:

    test_every_candidate_has_outcome_and_offtarget            passed
    test_every_candidate_has_all_axes                         passed
    test_every_candidate_axes_populated                       passed
    test_completeness_property                                passed
    ... eleven more

The suite as a whole would have caught it, loudly. These would have said the contract
held. A guard whose name matches a requirement is not evidence that it checks it, and
"my assertions never ran" is the one failure a green test cannot report.

This file is the mechanical version of the grep that found them: a test whose every
assertion is inside a loop over a *candidate collection* must first assert that the
collection is non-empty. It is deliberately narrow — loops over a fixed registry (`TASKS`,
`FIGURES`, `VECTOR_SCHEMES`) are exhaustive by construction and are not the shape that
went wrong.
"""

from __future__ import annotations

import ast
from pathlib import Path

_TESTS = Path(__file__).resolve().parent

#: Iterables that are a *computed result* of designing or reporting. A loop over one of
#: these is empty exactly when the thing under test produced nothing, which is the state
#: these tests exist to notice.
_CANDIDATE_SOURCES = ("candidates", "design_base_editor", "design_cas9", "design_prime")


def _is_candidate_source(node: ast.expr) -> bool:
    """Return whether ``node`` evaluates to a freshly computed candidate collection."""
    text = ast.unparse(node)
    if text.split("(")[0].split(".")[-1].lstrip("_").startswith("design"):
        return True
    return any(
        text.endswith(f".{name}") or text.startswith(f"{name}(") for name in _CANDIDATE_SOURCES
    )


def _asserts_non_emptiness(function: ast.FunctionDef | ast.AsyncFunctionDef, target: str) -> bool:
    """Return whether ``function`` asserts ``target`` (or its binding) is non-empty."""
    root = target.split(".")[0].split("(")[0]
    for node in ast.walk(function):
        if not isinstance(node, ast.Assert):
            continue
        text = ast.unparse(node.test)
        if (
            text == target
            or text == root
            or text.startswith(f"len({root}")
            or text.startswith(f"len({target}")
        ):
            return True
    return False


def _offenders() -> list[str]:
    found: list[str] = []
    for path in sorted(_TESTS.rglob("test_*.py")):
        if path.name == Path(__file__).name:
            continue
        tree = ast.parse(path.read_text())
        for function in ast.walk(tree):
            if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if not function.name.startswith("test"):
                continue
            asserts = [n for n in ast.walk(function) if isinstance(n, ast.Assert)]
            if not asserts:
                continue
            for loop in ast.walk(function):
                if not isinstance(loop, ast.For) or not _is_candidate_source(loop.iter):
                    continue
                in_loop = {id(n) for n in ast.walk(loop) if isinstance(n, ast.Assert)}
                if not in_loop or any(id(a) not in in_loop for a in asserts):
                    continue  # something outside the loop is asserted too
                if _asserts_non_emptiness(function, ast.unparse(loop.iter)):
                    continue
                rel = path.relative_to(_TESTS.parent).as_posix()
                found.append(f"{rel}:{function.lineno} {function.name}")
    return found


def test_no_test_asserts_only_inside_a_loop_over_candidates() -> None:
    offenders = _offenders()
    assert not offenders, (
        "these tests assert nothing when the design produces no candidates — bind the "
        "collection and assert it is non-empty before looping:\n  " + "\n  ".join(offenders)
    )


def test_the_reader_recognises_the_shape_it_is_looking_for() -> None:
    """Or a guard that found nothing would be indistinguishable from a guard that works."""
    module = ast.parse(
        "def test_x():\n    for c in menu.candidates:\n        assert c.efficiency is not None\n"
    )
    function = module.body[0]
    assert isinstance(function, ast.FunctionDef)
    loop = function.body[0]
    assert isinstance(loop, ast.For)
    assert _is_candidate_source(loop.iter)
    assert not _asserts_non_emptiness(function, "menu.candidates")


def test_the_reader_accepts_the_repaired_shape() -> None:
    module = ast.parse(
        "def test_x():\n"
        "    assert menu.candidates\n"
        "    for c in menu.candidates:\n"
        "        assert c.efficiency is not None\n"
    )
    function = module.body[0]
    assert isinstance(function, ast.FunctionDef)
    assert _asserts_non_emptiness(function, "menu.candidates")
