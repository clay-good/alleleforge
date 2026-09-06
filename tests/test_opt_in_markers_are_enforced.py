"""The opt-in markers must be enforced by a mechanism, not by a convention.

"CI stays weight-free" is a non-negotiable design principle, and the `real_weights`
marker's own description claims the marker does it: "opt-in, skipped in CI". It did
not. CI runs a bare `pytest` with no `-m "not real_weights"`, and what actually kept
the weights out was that each of the four such tests opened with its own hand-written
`pytest.skip` when the extra or the artifact was absent. Four correct guards and no
mechanism — a fifth test that forgot would download real model weights in a CI job.

The root `conftest.py` now skips them unless the opt-in variable is set, so the
marker's description is true. These run a throwaway suite under that conftest to pin
both halves: the marked test does not run by default, and it does run when opted in.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

_ROOT_CONFTEST = (Path(__file__).resolve().parents[1] / "conftest.py").read_text()

#: A suite with one marked test that fails loudly if it is ever collected and run, so
#: "skipped" and "silently passed" cannot be confused, plus an ordinary test so a
#: suite that skipped *everything* would not look like success either.
_SUITE = """
import pytest

@pytest.mark.real_weights
def test_needs_weights():
    raise AssertionError("must not run without the opt-in")

def test_ordinary():
    pass
"""

_INI = "[pytest]\nmarkers =\n    real_weights: opt-in\n    live_integration: opt-in\n"


def _prepare(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(_ROOT_CONFTEST)
    pytester.makepyfile(test_sample=_SUITE)
    pytester.makeini(_INI)


def test_a_marked_test_does_not_run_without_the_opt_in(pytester: pytest.Pytester) -> None:
    _prepare(pytester)
    pytester.runpytest_subprocess("-p", "no:cacheprovider").assert_outcomes(passed=1, skipped=1)


def test_the_opt_in_variable_lets_it_run(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An opt-in that cannot be opted into is just a deletion."""
    _prepare(pytester)
    monkeypatch.setenv("ALLELEFORGE_REAL_WEIGHTS", "1")
    pytester.runpytest_subprocess("-p", "no:cacheprovider").assert_outcomes(passed=1, failed=1)
