"""A run made population-aware over HTTP recorded nothing about the data that made it so.

The provenance block exists so a result can be re-derived, and `_collect_datasets` builds
it by reading a `dataset_version` descriptor off each supplied source. The CLI attached
one to every caller-supplied file it loaded — `--gnomad`, `--haplotypes` — pinning the
bytes by their content hash, because a file a user points at has no upstream version
string and what it *contained* is the only honest pin.

The web API loads the same two files, from `ALLELEFORGE_GNOMAD_TSV` and
`ALLELEFORGE_HAPLOTYPES`, and attached nothing. So the identical panel produced a
provenance block naming it from the command line and a silent one over HTTP: a served
result could be haplotype-aware, say so in its rationale, and record no pin for the panel
that made it so.

A statement-deletion sweep found the loose end — `HaplotypePanel.source` is set on every
construction and read by nobody — and following it to the consumer showed the descriptor
was simply never attached on this surface. Both shells now call one
`describe_file_source`, and `dataset_version` is a declared attribute on both loaders
rather than one bolted on from outside by whichever caller remembered.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from alleleforge.data.gnomad import GnomadDB
from alleleforge.data.haplotypes import HaplotypePanel
from alleleforge.types.provenance import describe_file_source

_PANEL = "#hap_id\tchrom\tstart\tend\tpopulation\tfrequency\tvariants\n"
_PANEL_ROW = "h1\tchr1\t100\t150\tEUR\t0.2\tchr1:120:A>G\n"


@pytest.fixture
def panel(tmp_path: Path) -> Path:
    path = tmp_path / "panel.tsv"
    path.write_text(_PANEL + _PANEL_ROW)
    return path


def test_a_loader_starts_with_no_descriptor(panel: Path) -> None:
    """The premise: the attribute is declared, and empty until a shell fills it."""
    assert HaplotypePanel.from_tsv(panel, source=str(panel)).dataset_version is None
    assert GnomadDB(()).dataset_version is None


def test_the_descriptor_pins_the_bytes_that_were_read(panel: Path) -> None:
    descriptor = describe_file_source(panel, "haplotype-panel")
    assert descriptor.sha256 == hashlib.sha256(panel.read_bytes()).hexdigest()
    assert descriptor.caller_supplied is True
    assert descriptor.name == "haplotype-panel"


def test_two_different_panels_pin_differently(tmp_path: Path) -> None:
    """A constant would satisfy the check above; this is what makes it a pin."""
    first, second = tmp_path / "a.tsv", tmp_path / "b.tsv"
    first.write_text(_PANEL + _PANEL_ROW)
    second.write_text(_PANEL + _PANEL_ROW.replace("0.2", "0.4"))
    assert (
        describe_file_source(first, "haplotype-panel").sha256
        != describe_file_source(second, "haplotype-panel").sha256
    )


@pytest.mark.parametrize("name", ["gnomad", "haplotype-panel"])
def test_both_shells_describe_a_file_the_same_way(panel: Path, name: str) -> None:
    """The CLI helper and the web loaders are the same function, not two copies.

    They were two copies, one of which existed. If they diverge again, the same file
    pins differently depending on which surface read it — and the provenance block's
    only job is that two runs agree iff the bytes did.
    """
    from alleleforge.cli.main import _describe_source

    assert _describe_source(panel, name) == describe_file_source(panel, name)


def test_the_served_haplotype_panel_carries_its_descriptor(
    panel: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alleleforge.web.api import app as app_module

    monkeypatch.setenv("ALLELEFORGE_HAPLOTYPES", str(panel))
    loaded = app_module._load_haplotypes_from_env()
    assert loaded, "the panel did not load; this check would be vacuous"
    assert loaded.dataset_version == describe_file_source(panel, "haplotype-panel")


def test_the_served_frequency_file_carries_its_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sites = tmp_path / "sites.tsv"
    sites.write_text("#chrom\tpos\tref\talt\taf\tnfe\nchr1\t120\tA\tG\t0.01\t0.02\n")
    from alleleforge.web.api import app as app_module

    monkeypatch.setenv("ALLELEFORGE_GNOMAD_TSV", str(sites))
    loaded = app_module._load_gnomad_from_env()
    assert loaded is not None, "the frequency file did not load"
    assert loaded.dataset_version == describe_file_source(sites, "gnomad")
