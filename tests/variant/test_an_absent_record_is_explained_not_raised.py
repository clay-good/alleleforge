"""An accession the supplied release does not contain was a raw traceback.

Once a release can be supplied, the likeliest thing to go wrong is supplying the wrong
one — a subset, a truncated download, a build predating the accession, or a file that
parsed into nothing. All four came out of `ClinVarDB.get` / `DbSnpDB.locus` as a
`KeyError` three frames down, on every shell, because the resolver caught `ValueError`
from its siblings and these two raise a different type. That is the shape this project
keeps finding: of N things doing one job, the unguarded one is picked out by its
*exception type*, not by its logic.

Fixed at the resolver, which is where Python, the command line and an HTTP request all
pass, so one decision serves all three.

The record count is the load-bearing detail. `0 record(s)` says the *file* is the
problem, not the accession, and nothing else in any output reveals that — a header-only
VCF from a truncated download parses perfectly and indexes nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.data.clinvar import ClinVarDB
from alleleforge.data.dbsnp import DbSnpDB
from alleleforge.types.provenance import DatasetVersion
from alleleforge.variant.resolver import resolve

_HEADER = "##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"


def _clinvar(tmp_path: Path, body: str = "") -> ClinVarDB:
    path = tmp_path / "clinvar.vcf"
    path.write_text(_HEADER + body)
    return ClinVarDB.from_vcf(path)


def _dbsnp(tmp_path: Path, body: str = "") -> DbSnpDB:
    path = tmp_path / "dbsnp.tsv"
    path.write_text("#rsid\tchrom\tpos\tref\talt\n" + body)
    return DbSnpDB.from_tsv(path)


@pytest.mark.parametrize(
    ("body", "held"),
    [
        ("", "0 record(s)"),  # a truncated download: parses fine, indexes nothing
        ("2\t60100\t17\tA\tT\t.\t.\tCLNSIG=Benign\n", "1 record(s)"),  # a subset
    ],
)
def test_a_missing_accession_is_explained(body: str, held: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError) as excinfo:
        resolve("VCV000000012", clinvar=_clinvar(tmp_path, body))
    message = str(excinfo.value)
    assert "VCV000000012" in message and held in message, message
    # The alternative that needs no database at all, as every other refusal here names it.
    assert "chrom:pos:ref>alt" in message, message


def test_a_missing_rsid_is_explained(tmp_path: Path) -> None:
    with pytest.raises(ValueError) as excinfo:
        resolve("rs999999", dbsnp=_dbsnp(tmp_path, "rs334\t2\t60100\tA\tT\n"))
    message = str(excinfo.value)
    assert "rs999999" in message and "1 record(s)" in message, message


def test_the_release_that_did_not_contain_it_is_named(tmp_path: Path) -> None:
    """Which of two releases was actually passed is not otherwise recoverable."""
    db = _clinvar(tmp_path)
    db.dataset_version = DatasetVersion(  # type: ignore[attr-defined]
        name="clinvar", version="sha256:feedface", caller_supplied=True
    )
    with pytest.raises(ValueError, match="sha256:feedface"):
        resolve("VCV000000012", clinvar=db)


def test_a_lookup_that_cannot_size_itself_still_explains(tmp_path: Path) -> None:
    """The Protocol requires one method; a stub need not be sized, and must not crash here."""

    class _Stub:
        def get(self, accession: object) -> object:
            raise KeyError("nope")

    with pytest.raises(ValueError) as excinfo:
        resolve("VCV000000012", clinvar=_Stub())  # type: ignore[arg-type]
    assert "unknown number of records" in str(excinfo.value), excinfo.value


@pytest.mark.parametrize("argv", [["resolve", "VCV000099999"], ["resolve", "rs999999"]])
def test_the_cli_reports_it_rather_than_a_traceback(argv: list[str], tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from alleleforge.cli.main import app

    clinvar = tmp_path / "clinvar.vcf"
    clinvar.write_text(_HEADER)
    dbsnp = tmp_path / "dbsnp.tsv"
    dbsnp.write_text("#rsid\tchrom\tpos\tref\talt\n")
    result = CliRunner().invoke(app, [*argv, "--clinvar", str(clinvar), "--dbsnp", str(dbsnp)])
    assert result.exit_code == 2, result.output
    output = result.output + result.stderr
    assert "Traceback" not in output, output
    assert "0 record(s)" in output, output
