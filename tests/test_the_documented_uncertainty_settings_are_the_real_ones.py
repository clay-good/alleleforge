"""The ensemble size and interval level are stated in prose seven times each.

`DEFAULT_ENSEMBLE_SIZE` and `DEFAULT_INTERVAL_LEVEL` are the shipped configuration. The
README, the concepts page, the preprint and — the one that matters most — the **model
card** for `cas9-efficiency-ensemble` all restate them as `N=5` and `80% interval`.
Nothing tied any of those to the constants.

A model card is a formal honesty artifact: it is what a reader consults to decide whether
to trust a number, and a card that describes an ensemble the code no longer runs is worse
than no card, because it looks like disclosure. The same goes for a preprint. Changing one
constant would have quietly falsified all of them, and the suite would have stayed green.

Restricted to Markdown and YAML: `docs/assets/figures/conformal_coverage.svg` legitimately
plots both calibration levels (80% and 90%), so it is a figure, not a claim about the
default.
"""

from __future__ import annotations

import re
from pathlib import Path

from alleleforge.scoring.uncertainty import DEFAULT_ENSEMBLE_SIZE, DEFAULT_INTERVAL_LEVEL

_ROOT = Path(__file__).resolve().parents[1]
_PROSE = (
    [_ROOT / "README.md"]
    + sorted((_ROOT / "docs").rglob("*.md"))
    + sorted((_ROOT / "src" / "alleleforge" / "model_zoo" / "cards").rglob("*.yaml"))
)


def _claims(pattern: str) -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    for path in _PROSE:
        for match in re.findall(pattern, path.read_text(encoding="utf-8")):
            found.append((path, match))
    return found


def test_every_stated_ensemble_size_is_the_shipped_one() -> None:
    claims = _claims(r"\bN=(\d+)\b")
    assert claims, "no ensemble size stated in prose — this check would be vacuous"
    for path, value in claims:
        assert int(value) == DEFAULT_ENSEMBLE_SIZE, (
            f"{path.relative_to(_ROOT)} says N={value}, the code ships "
            f"DEFAULT_ENSEMBLE_SIZE={DEFAULT_ENSEMBLE_SIZE}"
        )


def test_every_stated_interval_level_is_the_shipped_one() -> None:
    claims = _claims(r"(\d+)% (?:predictive )?intervals?\b")
    assert claims, "no interval level stated in prose — this check would be vacuous"
    expected = round(DEFAULT_INTERVAL_LEVEL * 100)
    for path, value in claims:
        assert int(value) == expected, (
            f"{path.relative_to(_ROOT)} says a {value}% interval, the code ships "
            f"DEFAULT_INTERVAL_LEVEL={DEFAULT_INTERVAL_LEVEL}"
        )


def test_the_card_metric_agrees_with_the_card_prose() -> None:
    """The card states the ensemble size twice — as prose and as a structured metric.

    `metrics.ensemble_size` is what a machine reads; the `N=5` in `training_data` is what
    a person reads. Nothing tied either to the code, and nothing tied them to each other.
    """
    from alleleforge.scoring.cas9_efficiency import EnsembleEfficiencyScorer

    card = EnsembleEfficiencyScorer().model_card()
    assert card.metrics["ensemble_size"] == float(DEFAULT_ENSEMBLE_SIZE)
    assert f"N={DEFAULT_ENSEMBLE_SIZE}" in card.training_data
