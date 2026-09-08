"""The likeliest first-run mistake was answered with a stack trace.

A variant naming a contig the reference does not have — a wrong assembly, a wrong
species, a typo, a VCF from another build — printed a rich traceback ending in
`KeyError: "unknown contig 'chrZ'"`, from `aforge resolve` and `aforge design` alike.

The project had already fixed this exact mistake from the other input. `--region chrZ:1-100`
answers with a sentence that names the offender, lists what the reference has, and says what
the consequence is; its docstring explains the choice — "Deliberately not a `KeyError` from
the fetch: the caller's mistake is the *region list*, and the fix is usually the panel's
assembly or its `chr` prefixing, neither of which a bare missing-key error suggests." The
same reference and the same absent contig, reached through a variant instead, gave a stack.

It was supposed to be handled. `_rename_contig_to_reference` leaves an unknown contig alone
"so the existing reference-base validation raises the error it already raises" — but that
validation reads the genome through `fetch_result`, which raises two frames deeper and as a
`KeyError`, so the intended message never ran. A comment describing a downstream check is
not the same as the check running first.

Fixed in the resolver rather than the CLI, which is the region round's other lesson: it
noted that "the CLI had this check and the library did not, so only one of three callers got
an answer they could act on".
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.variant.resolver import resolve

runner = CliRunner()


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    path = tmp_path / "ref.fa"
    path.write_text(">chr1\n" + "ACGT" * 100 + "\n", encoding="utf-8")
    return path


@pytest.fixture
def reference(fasta: Path) -> ReferenceGenome:
    return ReferenceGenome(fasta, build="hg38")


def test_the_library_refuses_with_a_message_not_a_key_error(reference: ReferenceGenome) -> None:
    with pytest.raises(ValueError) as raised:
        resolve("chrZ:101:A>G", reference=reference, build="hg38")
    message = str(raised.value)
    assert "chrZ" in message, "the refusal must name the contig that is missing"
    assert "chr1" in message, "and what the reference does have, so the fix is visible"
    assert "assembly" in message


def test_it_is_not_a_key_error_any_more(reference: ReferenceGenome) -> None:
    """`KeyError` is what leaked; a caller catching `ValueError` must now see it."""
    try:
        resolve("chrZ:101:A>G", reference=reference, build="hg38")
    except ValueError:
        pass
    except KeyError:  # pragma: no cover - the regression this pins
        pytest.fail("an unknown contig still escapes as a KeyError")


@pytest.mark.parametrize("command", ["resolve", "design"])
def test_no_command_prints_a_traceback(command: str, fasta: Path) -> None:
    result = runner.invoke(app, [command, "chrZ:101:A>G", "--reference-fasta", str(fasta)])
    combined = result.stdout + result.stderr
    assert "Traceback" not in combined, combined[:400]
    assert "KeyError" not in combined, combined[:400]
    assert result.exit_code != 0
    assert "chrZ" in combined and "chr1" in combined


def test_a_reconcilable_spelling_still_resolves(reference: ReferenceGenome) -> None:
    """The refusal must not catch the case naming reconciliation exists to handle."""
    assert resolve("1:101:A>G", reference=reference, build="hg38") is not None
    assert resolve("chr1:101:A>G", reference=reference, build="hg38") is not None


def test_the_wording_matches_the_region_refusal(reference: ReferenceGenome) -> None:
    """Two paths, one mistake: a reader should not have to learn two vocabularies."""
    from alleleforge.offtarget.engine import _reject_unknown_contigs
    from alleleforge.types.sequence import GenomicInterval, Strand

    with pytest.raises(ValueError) as region:
        _reject_unknown_contigs(
            [GenomicInterval(chrom="chrZ", start=0, end=10, strand=Strand.PLUS)],
            reference=reference,
        )
    with pytest.raises(ValueError) as variant:
        resolve("chrZ:101:A>G", reference=reference, build="hg38")

    for phrase in ("which this reference does not have", "it has:"):
        assert phrase in str(region.value), phrase
        assert phrase in str(variant.value), f"{phrase!r} missing from the variant refusal"
