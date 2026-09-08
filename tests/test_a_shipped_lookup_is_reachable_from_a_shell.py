"""A ClinVar accession and a dbSNP rsID were refused on a false premise.

Both refusals said the lookups were "Protocols with no shipped implementation, and the
registry lists no fetchable ClinVar or dbSNP release", so the honest remedy was to type
coordinates instead. The first half was never true:
:class:`~alleleforge.data.clinvar.ClinVarDB` and :class:`~alleleforge.data.dbsnp.DbSnpDB`
ship, are package exports, are covered by their own tests, and implement those Protocols
method for method. They are *file-backed*, like ``--gnomad`` — only the second half held,
and "we do not fetch it" is a different sentence from "it cannot be supplied".

The cost was the whole difference between an accession and a coordinate: ClinVar's
classification is why anyone types ``VCV000012345`` rather than ``chr11:5227002:A>T``,
and the resolver carries it into the menu rationale. That capability was Python-only,
and the reason it was Python-only had been written into a shell-parity guard's allowance
list, where nothing could re-open it.

What this file pins:

1. the shipped classes satisfy the Protocols, so the excuse cannot come back;
2. each shell runs the remedy its own refusal names (a remedy nobody tried is a guess);
3. what the accession was *for* — the clinical assertion — reaches the design; and
4. two releases that disagree about one rsID produce provenance that says so. A lookup
   decides *which locus the run is about*, so it is a dataset in the R214 sense.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app
from alleleforge.data.clinvar import ClinVarDB
from alleleforge.data.dbsnp import DbSnpDB
from alleleforge.variant.resolver import ClinVarLookup, DbSnpLookup, database_remedy

_SEQ = "ACGTTGCAAGGCTTACCGTA" * 20  # 400 bp of chr9


@pytest.fixture
def reference_fasta(tmp_path: Path) -> Path:
    fasta = tmp_path / "chr9.fa"
    fasta.write_text(">chr9\n" + _SEQ + "\n")
    return fasta


@pytest.fixture
def clinvar_vcf(tmp_path: Path) -> Path:
    """A one-record ClinVar release whose REF matches `_SEQ` at 1-based pos 101."""
    assert _SEQ[102] == "G", _SEQ[95:105]
    vcf = tmp_path / "clinvar.vcf"
    vcf.write_text(
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        "9\t103\t12\tG\tA\t.\t.\tCLNSIG=Pathogenic;GENEINFO=ABL1:25;RS=334\n"
    )
    return vcf


def _dbsnp_tsv(path: Path, *, pos: int, ref: str, alt: str) -> Path:
    path.write_text(f"#rsid\tchrom\tpos\tref\talt\nrs334\t9\t{pos}\t{ref}\t{alt}\n")
    return path


@pytest.mark.parametrize(
    ("protocol", "implementation"),
    [(ClinVarLookup, ClinVarDB), (DbSnpLookup, DbSnpDB)],
)
def test_the_shipped_classes_implement_the_resolver_protocols(
    protocol: type, implementation: type
) -> None:
    """The excuse was structural, so the refutation is too.

    Compared by method rather than with `isinstance`: these Protocols are not
    `runtime_checkable`, and making them so to satisfy a test would change the
    library to fit the check.
    """
    required = [
        name
        for name in vars(protocol)
        if not name.startswith("_") and callable(getattr(protocol, name, None))
    ]
    assert required, protocol
    for name in required:
        method = getattr(implementation, name, None)
        assert callable(method), f"{implementation.__name__} has no {name}()"
        # Parameter names, not the full signature: the annotations are written in
        # each file's own idiom (`str | DbSnpId` against `DbSnpId | str`) and the
        # types are already `mypy --strict`'s job at the call sites. What a test can
        # add is that the call shape matches.
        assert [p.name for p in inspect.signature(method).parameters.values()] == [
            p.name for p in inspect.signature(getattr(protocol, name)).parameters.values()
        ], name


@pytest.mark.parametrize(
    ("variant", "kind", "flag"),
    [("VCV000000012", "clinvar", "--clinvar"), ("rs334", "dbsnp", "--dbsnp")],
)
def test_the_refusal_names_a_flag_that_then_works(
    variant: str, kind: str, flag: str, tmp_path: Path, reference_fasta: Path, clinvar_vcf: Path
) -> None:
    """Refuse, read the remedy off the refusal, run it, succeed. In that order."""
    runner = CliRunner()
    bare = runner.invoke(app, ["resolve", variant, "--reference-fasta", str(reference_fasta)])
    assert bare.exit_code != 0
    assert flag in bare.output + bare.stderr, bare.output + bare.stderr
    assert flag in database_remedy(kind)

    db = (
        clinvar_vcf
        if kind == "clinvar"
        else _dbsnp_tsv(tmp_path / "dbsnp.tsv", pos=103, ref="G", alt="A")
    )
    ok = runner.invoke(
        app,
        ["resolve", variant, "--reference-fasta", str(reference_fasta), flag, str(db), "--json"],
    )
    assert ok.exit_code == 0, ok.output + ok.stderr
    payload = json.loads(ok.stdout)
    assert payload["variant"] == "chr9:102:G>A", payload
    # The release that chose the locus is pinned, not merely the input form.
    assert [d["name"] for d in payload["resolved_from"]] == [kind], payload


def test_the_classification_the_accession_was_chosen_for_reaches_the_menu(
    reference_fasta: Path, clinvar_vcf: Path
) -> None:
    """A coordinate could have been typed instead; the classification could not."""
    result = CliRunner().invoke(
        app,
        [
            "design",
            "VCV000000012",
            "--reference-fasta",
            str(reference_fasta),
            "--clinvar",
            str(clinvar_vcf),
            "--no-offtarget",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    report = json.loads(result.stdout)
    assert "ClinVar: pathogenic" in report["rationale"], report["rationale"]
    assert "clinvar" in [d["name"] for d in report["provenance"]["datasets"]]


def test_two_releases_that_disagree_produce_provenance_that_disagrees(
    tmp_path: Path, reference_fasta: Path
) -> None:
    """One rsID, two builds, two loci — the artifacts must be distinguishable."""
    assert _SEQ[102] == "G" and _SEQ[122] == "G"
    runs = []
    for name, pos in (("a", 103), ("b", 123)):
        db = _dbsnp_tsv(tmp_path / f"dbsnp_{name}.tsv", pos=pos, ref="G", alt="A")
        result = CliRunner().invoke(
            app,
            [
                "resolve",
                "rs334",
                "--reference-fasta",
                str(reference_fasta),
                "--dbsnp",
                str(db),
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output + result.stderr
        runs.append(json.loads(result.stdout))
    assert runs[0]["variant"] != runs[1]["variant"]
    assert runs[0]["resolved_from"] != runs[1]["resolved_from"], (
        "two dbSNP releases putting one rsID at two loci left an identical pin"
    )
