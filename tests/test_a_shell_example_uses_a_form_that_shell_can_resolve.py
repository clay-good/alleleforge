"""The flagship CLI example in the README could not run.

    aforge design VCV000012345 --reference-fasta hg38.fa …

    error: resolving a ClinVar accession requires a clinvar= database

At the time, the CLI had no code path that constructed the shipped `ClinVarDB` and
`DbSnpDB`, and the registry had no fetchable release. Three of the five input forms the
argument help advertised — accession, rsID, coding/protein HGVS — therefore could not be
used from either shell, and the two documented CLI examples plus one `curl` example used
the first of them. The file-backed CLI paths and a pinned ClinVar acquisition now exist;
this guard still ensures an example shows the lookup it needs.

The refusal made it worse by naming `clinvar=`, a *Python keyword argument*, to a caller
who arrived from a command line or a JSON body. A remedy the surface does not have is not
a remedy.

Python may still pass a lookup, and the Python snippets that do (`resolve("VCV…",
clinvar=clinvar_db)`) are correct and stay.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest

from alleleforge.variant.resolver import database_remedy

_ROOT = Path(__file__).resolve().parents[1]
_DOCS = [_ROOT / "README.md", *(_ROOT / "docs").rglob("*.md")]

#: Input forms that need a lookup database or the `hgvs` library, paired with the flag
#: that makes each form reachable from the CLI.
_REQUIRED_FLAGS = (
    (re.compile(r"^VCV\d+$"), "--clinvar"),
    (re.compile(r"^rs\d+$"), "--dbsnp"),
    (re.compile(r"^[A-Z_0-9.]+:[cp]\.\S+$"), "--hgvs"),
)


def _shell_variant_arguments() -> list[tuple[str, str, set[str]]]:
    """Return (file, variant, flags) for every variant-taking CLI example."""
    found: list[tuple[str, str, set[str]]] = []
    for path in _DOCS:
        buffer = ""
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not buffer and not line.startswith("aforge "):
                continue
            if line.endswith("\\"):
                buffer += line[:-1] + " "
                continue
            argv = shlex.split(buffer + line)
            buffer = ""
            command_index = next(
                (index for index, token in enumerate(argv) if token in {"design", "resolve"}),
                None,
            )
            if command_index is None or command_index + 1 >= len(argv):
                continue
            found.append(
                (
                    path.name,
                    argv[command_index + 1],
                    {token for token in argv if token.startswith("--")},
                )
            )
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
    if source == "cli":
        offenders = [
            (file, variant, required)
            for file, variant, flags in examples
            for pattern, required in _REQUIRED_FLAGS
            if pattern.match(variant) and required not in flags
        ]
    else:
        offenders = [
            (file, variant)
            for file, variant in examples
            if any(pattern.match(variant) for pattern, _ in _REQUIRED_FLAGS)
        ]
    assert not offenders, (
        f"documented {source} examples use an input form no shell can resolve: "
        f"{offenders}. Use coordinates, or show the required CLI lookup flag."
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
    """Listing five forms with no caveat is what put them in the examples.

    The caveat is what each form *needs*, not that it is unreachable: `--clinvar`,
    `--dbsnp` and `--hgvs` each turn one of them on, and the help says so rather than
    leaving a reader to discover at the prompt that their accession went nowhere.
    """
    import typer

    from alleleforge.cli.main import app

    root = typer.main.get_command(app)
    for command in ("design", "resolve"):
        params = root.commands[command].params  # type: ignore[attr-defined]
        variant = next(p for p in params if p.name == "variant")
        assert variant.help, command
        for flag in ("--clinvar", "--dbsnp", "--hgvs"):
            assert flag in variant.help, (command, flag, variant.help)
