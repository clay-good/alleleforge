"""Three loaders record their provenance on construction, and nobody read it back.

A statement-deletion sweep removed `self.source = source` from `HaplotypePanel` and
`self.source_build = ...` / `self.target_build = ...` from `Liftover`, and the whole
suite stayed green for all three. Each is a documented public attribute — the class
docstrings list them — and each answers the question a reader of a result has to ask:
*which panel made this haplotype-aware*, and *between which two builds were these
coordinates moved*.

They are pinned here as the public API they are documented to be. One of them deserves
a sentence more.

**`HaplotypePanel.source` has no reader anywhere in this project.** The provenance
collector reads `dataset_version`, which the CLI attaches separately with
`_attach_source`; `source` is set on every construction and consumed by nothing. On the
CLI path that is merely redundant. On the **web** path it is not: `app.py` builds the
panel with `HaplotypePanel.from_tsv(path, source=path)` and nothing attaches a
`dataset_version`, so a run made haplotype-aware over HTTP records *no descriptor for
the panel that made it so*, while the same run from the command line records one. That
asymmetry is a real gap and is left standing deliberately — closing it means deciding
what descriptor the web surface should write, which is a change to the provenance
artifact and the maintainer's call, not a test's.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.data.haplotypes import HaplotypePanel
from alleleforge.genome.coordinates import Liftover

_PANEL = "#hap_id\tchrom\tstart\tend\tpopulation\tfrequency\tvariants\n"


@pytest.fixture
def panel_tsv(tmp_path: Path) -> Path:
    path = tmp_path / "panel.tsv"
    path.write_text(_PANEL + "h1\tchr1\t100\t150\tEUR\t0.2\tchr1:120:A>G\n")
    return path


def test_a_panel_records_the_source_it_was_built_from(panel_tsv: Path) -> None:
    panel = HaplotypePanel.from_tsv(panel_tsv, source=str(panel_tsv))
    assert panel.source == str(panel_tsv)


def test_two_panels_from_different_files_do_not_share_a_source(tmp_path: Path) -> None:
    """A constant would satisfy the check above; this is what makes it a record."""
    first = tmp_path / "a.tsv"
    second = tmp_path / "b.tsv"
    for path in (first, second):
        path.write_text(_PANEL + "h1\tchr1\t100\t150\tEUR\t0.2\tchr1:120:A>G\n")
    a = HaplotypePanel.from_tsv(first, source=str(first))
    b = HaplotypePanel.from_tsv(second, source=str(second))
    assert a.source != b.source


def test_a_liftover_says_which_builds_it_moves_between() -> None:
    lift = Liftover(lambda chrom, pos: [], source_build="hg19", target_build="hg38")
    assert lift.source_build == "hg19"
    assert lift.target_build == "hg38"


def test_the_two_builds_are_not_the_same_field() -> None:
    """Each recorded separately: a lift that reported one twice names no direction."""
    lift = Liftover(lambda chrom, pos: [], source_build="hg38", target_build="mm39")
    assert (lift.source_build, lift.target_build) == ("hg38", "mm39")
