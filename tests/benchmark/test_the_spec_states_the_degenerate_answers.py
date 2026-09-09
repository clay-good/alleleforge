"""The spec required `0.0` where the code now returns `None`, and nothing compared them.

Two rounds ago the ranking metrics stopped answering `0.0` for inputs that determine no
value. The **spec** went on requiring it:

> the worst value is `0.0` (and ECE returns `null`) … `spearman`/`pearson`/`roc_auc`/
> `pr_auc` return the degenerate `0.0`

A shipped contract that contradicts the shipped code is worse than a missing one. The next
person to read it reads an argument for putting the defect back — and the CLI spec has been
checked against the real CLI for hundreds of rounds while this one was checked against
nothing (no test in this repo referenced `benchmark-harness/spec.md` at all).

So the spec now carries one machine-readable line per metric, and this file calls each
metric with a degenerate input and holds the line to the answer. The degenerate inputs are
listed here rather than derived, because "what does not determine this metric" is different
for each of them — a single-class fold for AUROC, a constant series for a correlation — and
that difference is the thing worth stating.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import pytest

from alleleforge.benchmark import metrics as M

_SPEC = (
    Path(__file__).resolve().parents[2] / "openspec" / "specs" / "benchmark-harness" / "spec.md"
).read_text(encoding="utf-8")

#: One degenerate call per metric: an input that determines no value for *that* metric.
_DEGENERATE_CALLS: dict[str, Any] = {
    "spearman": lambda: M.spearman([1.0, 2.0, 3.0], [7.0, 7.0, 7.0]),  # constant predictions
    "pearson": lambda: M.pearson([1.0, 2.0, 3.0], [7.0, 7.0, 7.0]),
    "roc_auc": lambda: M.roc_auc([0.9, 0.8], [1, 1]),  # one class only
    "pr_auc": lambda: M.pr_auc([0.9, 0.1], [0, 0]),  # no positives
    "expected_calibration_error": lambda: M.expected_calibration_error([], []),
    "interval_calibration_error": lambda: M.interval_calibration_error([], [], nominal=0.8),
    "topk_accuracy": lambda: M.topk_accuracy({}, {}),  # nothing predicted, nothing observed
    "kl_divergence": lambda: M.kl_divergence({"a": 1.0}, {"a": float("nan")}),  # corrupt mass
}


def _stated_answers() -> dict[str, str]:
    """Return the answer the spec states for each metric, from its own bullet list."""
    stated = dict(re.findall(r"^- `(\w+)`: (undefined|`\+inf`|`0\.0`)$", _SPEC, re.M))
    assert len(stated) >= 6, f"parsed {stated} — the spec's metric list moved or changed shape"
    return stated


def test_the_spec_lists_every_metric_this_file_exercises() -> None:
    """Neither side may quietly shrink: a metric dropped from the list is unchecked."""
    assert set(_stated_answers()) == set(_DEGENERATE_CALLS), (
        sorted(_stated_answers()),
        sorted(_DEGENERATE_CALLS),
    )


@pytest.mark.parametrize("metric", sorted(_DEGENERATE_CALLS))
def test_the_code_gives_the_answer_the_spec_states(metric: str) -> None:
    stated = _stated_answers()[metric]
    actual = _DEGENERATE_CALLS[metric]()
    if stated == "undefined":
        assert actual is None, f"the spec says {metric} is undefined; it returned {actual!r}"
    elif stated == "`+inf`":
        assert actual == math.inf, f"the spec says {metric} is +inf; it returned {actual!r}"
    else:
        assert actual == 0.0, f"the spec says {metric} is 0.0; it returned {actual!r}"


def test_the_spec_no_longer_requires_the_placeholder_it_used_to() -> None:
    """The sentence that mandated the removed behaviour, named so it cannot come back."""
    assert "return the degenerate `0.0`" not in _SPEC, (
        "the spec requires the ranking metrics to answer 0.0 for a degenerate input, "
        "which the code no longer does and should not"
    )
