"""The one clause of the search description a caller can act on.

`search_description()` is one sentence carrying the mismatch budget, the reporting
cut-offs, the sub-threshold tail, the PAM broadening, the MAF cut-off and — at the end —
that every supplied population record was for another assembly. Six of those describe what
the scan *did*. The seventh says **you gave it the wrong file**, and it is the only one with
a remedy, sitting at the end of a seven-hundred-character paragraph in neutral text.

`aforge offtarget` already elevates the other actionable clause — the unexcluded on-target
locus — out of the paragraph and onto its headline in brackets. This follows that
precedent, and the page gets the same fact in the hazard style it uses for caveats, above
the paragraph rather than inside it.

Short on purpose: the paragraph keeps the full explanation, and a headline that repeats it
is a headline nobody reads.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.data.gnomad import GnomadDB
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM
from alleleforge.types.offtarget import build_mismatch_note

_SPACER = "ACCTGACTCCTGAGGAGAAG"
_ALT = {"A": "G", "G": "A", "C": "T", "T": "C"}


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    import random

    random.seed(11)
    seq = list("".join(random.choice("ACGT") for _ in range(4000)))
    seq[1000:1023] = list(_SPACER + "TGG")
    path = tmp_path / "ref.fa"
    body = "".join(seq)
    path.write_text(
        ">chr11\n" + "\n".join(body[i : i + 60] for i in range(0, len(body), 60)) + "\n"
    )
    return path


def _base(fasta: Path, one_based: int) -> str:
    import pyfaidx

    return str(pyfaidx.Fasta(str(fasta))["chr11"][one_based - 1 : one_based]).upper()


def _report(fasta: Path, tmp_path: Path, *, agreeing: bool) -> object:
    rows = []
    for pos in (1100, 1200):
        base = _base(fasta, pos)
        ref, alt = (base, _ALT[base]) if agreeing else (_ALT[base], base)
        rows.append(f"chr11\t{pos}\t{ref}\t{alt}\t0.02\t0.055\t0.0008")
    path = tmp_path / f"{'right' if agreeing else 'wrong'}.tsv"
    path.write_text("#chrom\tpos\tref\talt\taf\tafr\tnfe\n" + "\n".join(rows) + "\n")
    return search(
        _SPACER,
        PAM(pattern="NGG"),
        reference=ReferenceGenome(fasta, build="hg38"),
        gnomad=GnomadDB.from_sites_tsv(path),
        populations=["afr", "nfe"],
    )


def test_the_note_states_how_many_of_how_many(fasta: Path, tmp_path: Path) -> None:
    note = build_mismatch_note(_report(fasta, tmp_path, agreeing=False))
    assert note == "gnomad: 2 of 2 record(s) are for another build"


def test_it_is_absent_when_the_records_agree(fasta: Path, tmp_path: Path) -> None:
    assert build_mismatch_note(_report(fasta, tmp_path, agreeing=True)) is None


def test_it_is_shorter_than_the_paragraph_it_is_lifted_from(fasta: Path, tmp_path: Path) -> None:
    """A headline that repeats the paragraph is a headline nobody reads."""
    report = _report(fasta, tmp_path, agreeing=False)
    note = build_mismatch_note(report)
    assert note is not None
    assert len(note) < len(report.search_description()) / 4  # type: ignore[attr-defined]


def test_the_paragraph_still_carries_the_full_sentence(fasta: Path, tmp_path: Path) -> None:
    """Elevating a fact must not move it: the description is what travels in artifacts."""
    description = _report(fasta, tmp_path, agreeing=False).search_description()  # type: ignore[attr-defined]
    assert "not an absence of population risk" in description


def test_both_shells_show_it_beside_the_numbers() -> None:
    """The CLI headline and the page's result block, which are the two documents here."""
    from alleleforge.cli import main as cli_main

    source = Path(cli_main.__file__).read_text(encoding="utf-8")
    assert "mismatch_note" in source, "the CLI headline does not carry it"

    app_js = (
        Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend" / "app.js"
    ).read_text(encoding="utf-8")
    assert "data.build_mismatch" in app_js, "the page does not carry it"
    index = app_js.index("data.build_mismatch")
    assert 'class="err"' in app_js[index : index + 200], "the page renders it as neutral text"
