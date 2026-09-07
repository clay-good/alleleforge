"""The cache built for cohorts was the one thing a cohort could not use.

`OffTargetCache`'s own docstring opens with the case it exists for: "a cohort re-runs
the *same* guide against the *same* reference constantly". `aforge offtarget` could ask
for it. `aforge design` and `aforge batch` could not, because `design()` took neither
the cache nor the persistent genome index and so neither reached the three chemistry
verticals that actually run the search — which is where a cohort's off-target work is.

Both are threaded through now. Neither may change a result: a cohort that reuses work
must report exactly what a cold one reports, or the reuse is a correctness bug wearing a
performance flag.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app
from alleleforge.offtarget.cache import OffTargetCache

runner = CliRunner()

_VARIANT = "chr1:101:A>G"


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    rng = random.Random(11)
    seq = list(rng.choice("ACGT") for _ in range(3000))
    seq[100] = "A"
    path = tmp_path / "ref.fa"
    path.write_text(">chr1\n" + "".join(seq) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """This test's own cache root — `get_settings()` is a load-once singleton."""
    import alleleforge.config as config

    root = tmp_path / "cache"
    monkeypatch.setattr(config, "_SETTINGS", None)
    monkeypatch.setenv("ALLELEFORGE_CACHE_DIR", str(root))
    return root


def _design(fasta: Path, *extra: str) -> dict[str, object]:
    result = runner.invoke(
        app, ["design", _VARIANT, "--reference-fasta", str(fasta), "--json", *extra]
    )
    assert result.exit_code == 0, result.output
    report: dict[str, object] = json.loads(result.stdout)
    provenance = report.get("provenance")
    if isinstance(provenance, dict):
        provenance.pop("timestamp", None)
    return report


def test_a_reused_scan_designs_the_same_menu(fasta: Path, cache_dir: Path) -> None:
    cold = _design(fasta)
    warmed = _design(fasta, "--cache")
    again = _design(fasta, "--cache")
    assert warmed == cold, "--cache changed the menu"
    assert again == cold, "the run served from the cache changed the menu"


def test_the_persistent_index_designs_the_same_menu(fasta: Path, cache_dir: Path) -> None:
    assert _design(fasta, "--genome-index") == _design(fasta)


def test_designing_stores_scans_a_later_run_can_use(fasta: Path, cache_dir: Path) -> None:
    _design(fasta, "--cache")
    assert len(OffTargetCache()) > 0, "a design run with --cache stored no reference scan"


def test_a_design_run_without_the_flag_stores_nothing(fasta: Path, cache_dir: Path) -> None:
    _design(fasta)
    assert len(OffTargetCache()) == 0


def test_the_cohort_command_offers_what_the_single_variant_one_does(
    fasta: Path, cache_dir: Path, tmp_path: Path
) -> None:
    """The project's cohort-parity rule: a cohort is where reuse matters most."""
    variants = tmp_path / "variants.txt"
    variants.write_text(f"{_VARIANT}\n", encoding="utf-8")
    result = runner.invoke(
        app,
        ["batch", str(variants), "--reference-fasta", str(fasta), "--cache", "--genome-index"],
    )
    assert result.exit_code == 0, result.output
    assert len(OffTargetCache()) > 0, "a cohort run with --cache stored no reference scan"
