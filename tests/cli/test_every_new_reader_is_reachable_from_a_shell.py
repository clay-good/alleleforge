"""The readers added in R701-704 had to be reachable, and two were not.

Rounds 701 to 704 gave every dataset a reader for the artifact its upstream actually
publishes. That created the gap this project has found more often than any other: **a
capability the library has that no shell can reach.** Having just closed six instances of
the mirror image, I left two of these behind.

* `HaplotypePanel.from_phased_vcf` was reachable from **neither** shell. Both the CLI's
  `--haplotypes` and the web API's `ALLELEFORGE_HAPLOTYPES` called `from_tsv`, so last
  round's feature — building panels from the phased VCFs 1000G and HGDP publish — could
  only be used by importing the library.
* The web API still called `EncodeTracks.from_bedgraph`, so it could read only a format
  ENCODE does not serve, while the CLI had been moved to `load`.

The haplotype fix is not a flag swap, and the reason is worth keeping: `from_phased_vcf`
needs a phased VCF, a sample-to-population table **and** a window, which is more than a
design-time flag can carry, and the CLI loads its panel before any window is known.
`aforge data haplotypes` converts instead, writing the panel TSV that *both* surfaces
already load — so one command reaches every shell rather than a new pair of flags on each.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app

_PED = """\
FamilyID SampleID FatherID MotherID Sex Population Superpopulation
HG00096 HG00096 0 0 1 GBR EUR
NA19625 NA19625 0 0 2 ASW AFR
"""

_VCF = """\
##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tHG00096\tNA19625
chr22\t101\t.\tG\tC\t.\tPASS\t.\tGT\t0|1\t1|0
chr22\t201\t.\tA\tT\t.\tPASS\t.\tGT\t0|1\t0|0
"""


@pytest.fixture
def inputs(tmp_path: Path) -> tuple[Path, Path]:
    vcf = tmp_path / "phased.vcf"
    vcf.write_text(_VCF)
    ped = tmp_path / "samples.txt"
    ped.write_text(_PED)
    return vcf, ped


def test_a_phased_vcf_becomes_a_panel_a_shell_can_load(
    runner: CliRunner, inputs: tuple[Path, Path], tmp_path: Path
) -> None:
    """The whole round trip: VCF in, panel TSV out, loadable by `--haplotypes`.

    Asserted end to end rather than by checking the command exists, because "reachable"
    means the output feeds the surface that consumes it — a converter whose TSV the
    loader rejected would satisfy a weaker test and nothing else.
    """
    vcf, ped = inputs
    out = tmp_path / "panel.tsv"

    result = runner.invoke(
        app,
        [
            "data",
            "haplotypes",
            str(vcf),
            "--samples",
            str(ped),
            "--region",
            "chr22:0-1000",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == ExitCode.OK, result.output
    assert out.is_file()

    from alleleforge.data.haplotypes import HaplotypePanel

    panel = HaplotypePanel.from_tsv(out, source="1000g")
    assert list(panel), "the converter wrote a panel the loader reads as empty"
    assert {p for hap in panel for p in hap.frequencies} == {"EUR", "AFR"}


def test_the_region_is_required_rather_than_guessed(
    runner: CliRunner, inputs: tuple[Path, Path], tmp_path: Path
) -> None:
    """A haplotype is defined over a window, so there is no default to fall back on.

    Typer refuses the missing option itself; what matters is that the command does not
    quietly choose a span, because "the haplotypes of chromosome 22" is not a thing and
    choosing one would answer a question the caller did not ask.
    """
    vcf, ped = inputs
    result = runner.invoke(
        app,
        ["data", "haplotypes", str(vcf), "--samples", str(ped), "--out", str(tmp_path / "p.tsv")],
    )
    assert result.exit_code != ExitCode.OK
    assert "--region" in result.output + (result.stderr or "")


def test_a_window_with_no_variants_is_refused_not_written_empty(
    runner: CliRunner, inputs: tuple[Path, Path], tmp_path: Path
) -> None:
    """An empty panel loads as "no haplotypes", which reads as "no population risk".

    That is the quiet failure this project guards against everywhere else: a file that
    parses, carries nothing, and makes a scan look clean. Refused with the likely cause
    named.
    """
    vcf, ped = inputs
    result = runner.invoke(
        app,
        [
            "data",
            "haplotypes",
            str(vcf),
            "--samples",
            str(ped),
            "--region",
            "chr22:500000-501000",
            "--out",
            str(tmp_path / "p.tsv"),
        ],
    )
    assert result.exit_code == ExitCode.MISSING_DATA, result.output
    assert "no haplotypes" in result.output + (result.stderr or "")


def test_a_tab_split_sample_table_is_refused_with_the_reason(
    runner: CliRunner, inputs: tuple[Path, Path], tmp_path: Path
) -> None:
    """The sample table is space-separated, and a reader that gets it wrong finds nobody.

    Without this refusal the command would build a panel over zero samples, write an
    empty file, and report success — the same quiet failure as above, arriving from a
    one-character format difference.
    """
    vcf, _ = inputs
    empty_table = tmp_path / "nobody.txt"
    empty_table.write_text("FamilyID SampleID FatherID MotherID Sex Population Superpopulation\n")

    result = runner.invoke(
        app,
        [
            "data",
            "haplotypes",
            str(vcf),
            "--samples",
            str(empty_table),
            "--region",
            "chr22:0-1000",
            "--out",
            str(tmp_path / "p.tsv"),
        ],
    )
    assert result.exit_code == ExitCode.USAGE, result.output
    assert "names no samples" in result.output + (result.stderr or "")


# -- the shells use the readers that accept what upstream publishes ------------


@pytest.mark.parametrize(
    "module, forbidden, required",
    [
        ("alleleforge.cli.main", "GnomadDB.from_sites_tsv", "GnomadDB.load"),
        ("alleleforge.cli.main", "DbSnpDB.from_tsv", "DbSnpDB.load"),
        ("alleleforge.cli.main", "EncodeTracks.from_bedgraph", "EncodeTracks.load"),
        ("alleleforge.web.api.app", "GnomadDB.from_sites_tsv", "GnomadDB.load"),
        ("alleleforge.web.api.app", "EncodeTracks.from_bedgraph", "EncodeTracks.load"),
    ],
)
def test_a_shell_calls_the_reader_that_accepts_the_published_artifact(
    module: str, forbidden: str, required: str
) -> None:
    """Each shell must call the sniffing reader, not the single-format one.

    Read off the source rather than exercised, deliberately: these are one-line call
    sites and the failure mode is a *regression to the narrower reader*, which no
    behavioural test over project-format fixtures would notice. The web API's ENCODE
    loader was exactly that — left on `from_bedgraph` while the CLI moved on.
    """
    source = inspect.getsource(__import__(module, fromlist=["_"]))
    assert required in source, f"{module} no longer calls {required}"
    assert forbidden not in source, (
        f"{module} calls {forbidden}, which accepts only one format. Use {required}, "
        "which sniffs: upstream publishes the other one."
    )
