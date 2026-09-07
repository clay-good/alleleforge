"""Three surfaces take an interval from a user, and one of them used to skip the check.

An interval naming no bases restricts a search to nothing and reports every guide as
perfectly specific. Three places accept one from outside the process, and each refuses it
in its own words:

    GenomicInterval.parse    "locus 'chr1:100-100' is empty (100 <= 100)"
    Region.to_interval       "region chr1:100-100 is empty"
    read_bed_intervals       "line 1: interval names no bases (100 <= 100)"

They agree now. They did not before: the BED reader was written inline in the CLI and
constructed intervals directly, so `--region chr1:100-100` was a usage error while the
same row in a panel file was accepted — on one command. `GenomicInterval.parse`'s own
docstring claims to be "shared by every surface that accepts a locus from a user", which
was true of the surfaces its author had in view.

Three implementations of one rule is how a rule stops holding, and this one has already
demonstrated it. The list below is the enumeration that claim needs: a new surface that
takes an interval from a user has to appear here, and every entry has to refuse.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


#: Every way an interval reaches this tool from outside the process, as
#: (name, callable taking (chrom, start, end)). A surface missing from this list is a
#: surface nothing checks.
def _via_locus_string(chrom: str, start: int, end: int) -> Any:
    from alleleforge.types.sequence import GenomicInterval

    return GenomicInterval.parse(f"{chrom}:{start}-{end}")


def _via_web_region(chrom: str, start: int, end: int) -> Any:
    pytest.importorskip("fastapi")
    from alleleforge.web.api.models import Region

    return Region(chrom=chrom, start=start, end=end).to_interval()


def _via_bed(tmp_path: Path):  # noqa: ANN202 - a factory, typed at the call site
    def _read(chrom: str, start: int, end: int) -> Any:
        from alleleforge.genome.bed import read_bed_intervals

        path = tmp_path / "panel.bed"
        path.write_text(f"{chrom}\t{start}\t{end}\n")
        return read_bed_intervals(path)[0]

    return _read


def _surfaces(tmp_path: Path) -> dict[str, Any]:
    return {
        "locus string": _via_locus_string,
        "web region": _via_web_region,
        "bed row": _via_bed(tmp_path),
    }


def test_all_three_surfaces_are_enumerated(tmp_path: Path) -> None:
    assert len(_surfaces(tmp_path)) == 3


@pytest.mark.parametrize("name", ["locus string", "web region", "bed row"])
def test_an_empty_interval_is_refused(name: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _surfaces(tmp_path)[name]("chr1", 100, 100)


@pytest.mark.parametrize("name", ["locus string", "web region", "bed row"])
def test_an_inverted_interval_is_refused(name: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _surfaces(tmp_path)[name]("chr1", 200, 100)


@pytest.mark.parametrize("name", ["locus string", "web region", "bed row"])
def test_a_real_interval_survives_all_three(name: str, tmp_path: Path) -> None:
    """Refusing identically is only half of agreeing."""
    interval = _surfaces(tmp_path)[name]("chr1", 100, 200)
    assert (interval.chrom, interval.start, interval.end) == ("chr1", 100, 200)


def test_the_refusals_all_explain_the_same_thing(tmp_path: Path) -> None:
    """Different wording is fine; each must say the interval names no bases."""
    for name, call in _surfaces(tmp_path).items():
        with pytest.raises(ValueError) as excinfo:
            call("chr1", 100, 100)
        message = str(excinfo.value).lower()
        assert "empty" in message or "no bases" in message, (name, message)
