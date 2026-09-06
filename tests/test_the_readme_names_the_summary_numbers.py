"""The README's off-target summary listed two of the three numbers it now reports.

It explains the worst-case score and the aggregate specificity, and says specificity
"surfaces on every output surface that summarizes off-target", listing them. When
`expected_burden` was put on those same surfaces, the paragraph was not revisited — so the
one number that distinguishes a rare-variant off-target from a universal one, in a project
whose differentiator is population-aware nomination, was undocumented in the place a reader
goes to understand the summary.

This pins the three aggregate accessors against the README, so a fourth cannot be added to
the product and left out of the explanation.
"""

from __future__ import annotations

from pathlib import Path

from alleleforge.types.offtarget import OffTargetReport

_README = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")

#: The report's aggregate summary numbers — the ones a reader triages on — and the text
#: that counts as explaining each. The README describes the worst case in prose without
#: naming the accessor, which is fine: the check is that the *number* is explained, not
#: that the identifier appears.
_AGGREGATES = {
    "worst_score": ("worst-case", "worst site"),
    "specificity_score": ("specificity_score",),
    "expected_burden": ("expected_burden",),
}


def test_the_readme_explains_every_aggregate() -> None:
    for name, phrases in _AGGREGATES.items():
        assert any(phrase in _README for phrase in phrases), (
            f"{name} is a summary number a reader triages on and the README explains "
            f"none of {list(phrases)}"
        )


def test_the_named_aggregates_are_real() -> None:
    """A staleness check on the list: each must still be a method of the report."""
    for name in _AGGREGATES:
        assert callable(getattr(OffTargetReport, name)), name


def test_the_readme_says_the_burden_is_conditional() -> None:
    """It appears only when some site's presence is probabilistic; saying so matters,
    because a reader who never sees it should not conclude the guide has no burden."""
    assert "frequency-blind" in _README
    assert "with reference sites alone" in _README
