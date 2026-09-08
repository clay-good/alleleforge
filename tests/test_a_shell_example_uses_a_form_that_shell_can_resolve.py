"""The flagship CLI example in the README could not run.

    aforge design VCV000012345 --reference-fasta hg38.fa …

    error: resolving a ClinVar accession requires a clinvar= database

`ClinVarLookup` and `DbSnpLookup` are Protocols with no shipped implementation. The CLI
has no code path that constructs one, `create_app` takes no such argument, and the
registry lists no fetchable ClinVar or dbSNP release. So three of the five input forms
the argument help advertised — accession, rsID, coding/protein HGVS — cannot be used from
either shell, and the two documented CLI examples plus one `curl` example used the first
of them.

The refusal made it worse by naming `clinvar=`, a *Python keyword argument*, to a caller
who arrived from a command line or a JSON body. A remedy the surface does not have is not
a remedy.

Python may still pass a lookup, and the Python snippets that do (`resolve("VCV…",
clinvar=clinvar_db)`) are correct and stay.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from alleleforge.variant.resolver import database_remedy

_ROOT = Path(__file__).resolve().parents[1]
_DOCS = [_ROOT / "README.md", *(_ROOT / "docs").rglob("*.md")]

#: Input forms that need a lookup database or the `hgvs` library, which no shell supplies.
_NEEDS_A_DATABASE = re.compile(r"^(VCV\d+|rs\d+|[A-Z_0-9.]+:[cp]\.\S+)$")


def _shell_variant_arguments() -> list[tuple[str, str]]:
    """Return (file, variant) for every `aforge <cmd> <variant>` in the docs."""
    found: list[tuple[str, str]] = []
    for path in _DOCS:
        for match in re.finditer(
            r"^\s*aforge\s+(?:--\S+\s+\S+\s+)*(design|resolve|batch)\s+(\S+)",
            path.read_text(encoding="utf-8"),
            re.M,
        ):
            found.append((path.name, match.group(2).strip("'\"")))
    return found


def _json_variant_literals() -> list[tuple[str, str]]:
    """Return (file, variant) for every variant inside a documented request body."""
    found: list[tuple[str, str]] = []
    for path in _DOCS:
        text = path.read_text(encoding="utf-8")
        for block in re.findall(r'"variants?"\s*:\s*(\[[^\]]*\]|"[^"]*")', text):
            for value in re.findall(r'"([^"]+)"', block):
                found.append((path.name, value))
    return found


def test_the_scan_finds_examples() -> None:
    assert _shell_variant_arguments(), "no `aforge <cmd> <variant>` examples found"
    assert _json_variant_literals(), "no documented request bodies found"


@pytest.mark.parametrize("source", ["cli", "json"])
def test_no_documented_example_uses_a_form_its_shell_cannot_resolve(source: str) -> None:
    examples = _shell_variant_arguments() if source == "cli" else _json_variant_literals()
    offenders = [(f, v) for f, v in examples if _NEEDS_A_DATABASE.match(v)]
    assert not offenders, (
        f"documented {source} examples use an input form no shell can resolve: "
        f"{offenders}. Use coordinates, or show it as Python passing a lookup."
    )


def test_the_refusal_names_a_remedy_this_caller_has() -> None:
    """Not `clinvar=`: a keyword argument is not something a command line can pass."""
    for kind, flag, factory in (
        ("clinvar", "--clinvar", "ClinVarDB.from_vcf"),
        ("dbsnp", "--dbsnp", "DbSnpDB.from_tsv"),
    ):
        remedy = database_remedy(kind)
        assert "clinvar=" not in remedy and "dbsnp=" not in remedy
        # Each caller is told what *it* can do: a flag for the command line, a
        # constructor for Python, and for HTTP the reason there is no third option.
        assert flag in remedy, remedy
        assert factory in remedy, remedy
        assert "chrom:pos:ref>alt" in remedy, remedy
        assert "Over HTTP" in remedy, remedy


@pytest.mark.parametrize("bad", ["VCV000012345", "rs334"])
def test_the_refusal_reaches_a_cli_caller(bad: str, tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from alleleforge.cli.main import app

    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr1\n" + "ACGT" * 50 + "\n")
    result = CliRunner().invoke(app, ["resolve", bad, "--reference-fasta", str(fasta)])
    assert result.exit_code != 0
    output = result.output + result.stderr
    assert "chrom:pos:ref>alt" in output, output
    assert "clinvar=" not in output and "dbsnp=" not in output, output


def test_the_argument_help_does_not_advertise_them_unqualified() -> None:
    """Listing five forms with no caveat is what put them in the examples."""
    import typer

    from alleleforge.cli.main import app

    root = typer.main.get_command(app)
    for command in ("design", "resolve"):
        params = root.commands[command].params  # type: ignore[attr-defined]
        variant = next(p for p in params if p.name == "variant")
        assert variant.help, command
        assert "no way to supply" in variant.help, (command, variant.help)
