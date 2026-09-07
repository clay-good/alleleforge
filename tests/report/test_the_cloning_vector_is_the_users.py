"""The insert is screened against the enzyme the user's own vector uses.

`oligos_for` screens every insert for a copy of the Type IIS recognition site of the
scheme's enzyme — the classic Golden-Gate hazard, where the enzyme that assembles the
construct also cuts it and the clone silently fails. The screen is only as right as the
scheme, and the scheme was not askable:

    aforge design ...           -> screened for BsmBI (lentiGuide), always
    build_report(scheme=...)    -> Python only

pX330 / pSpCas9(BB) is the other standard sgRNA protocol and cuts with **BbsI**. Its
overhangs are the same `CACC`/`AAAC`, so the oligos the tool prints are correct to
order — and a spacer carrying `GAAGAC` was reported clean, because the shipped screen
was looking for `CGTCTC`. The vector is the user's fact, not the tool's.

A pegRNA needs an acceptor with 3'-extension overhangs, which an sgRNA-only vector has
none of, so naming one leaves pegRNA candidates on the pegRNA acceptor rather than
failing the whole report. Every candidate's rendered block names the scheme it used, so
the two are distinguishable on the page.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app
from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.report.builder import build_report
from alleleforge.report.oligos import (
    LENTIGUIDE_BSMBI,
    PEGRNA_GG_BSAI,
    PX330_BBSI,
    TYPE_IIS_SITES,
    VECTOR_SCHEMES,
    scheme_by_name,
)
from alleleforge.report.pdf import render_pdf

#: A 20-nt spacer carrying BbsI's `GAAGAC` and neither BsmBI's `CGTCTC` nor BsaI's
#: `GGTCTC`. The whole point of the fixture is that one enzyme sees a site here and
#: the others do not, so the asymmetry is asserted rather than assumed.
_BBSI_SPACER = "ACCTGAAGACTTACGCATAC"

#: Where the fixture drops that spacer (0-based) and the knock-out target inside it,
#: written as a VCF-style 1-based `chrom:pos:ref>alt` from the spacer itself so the
#: asserted ref base cannot drift away from the sequence the FASTA holds.
_SPACER_START = 1000
_TARGET_OFFSET = 17
_VARIANT = f"chr1:{_SPACER_START + _TARGET_OFFSET + 1}:{_BBSI_SPACER[_TARGET_OFFSET]}>A"


@pytest.fixture
def bbsi_fasta(tmp_path: Path) -> Path:
    """A FASTA whose knock-out guides carry a BbsI site and an NGG PAM."""
    rng = random.Random(7)
    seq = [rng.choice("ACGT") for _ in range(3_000)]
    seq[_SPACER_START : _SPACER_START + 23] = list(_BBSI_SPACER + "TGG")
    fasta = tmp_path / "bbsi.fa"
    fasta.write_text(">chr1\n" + "".join(seq) + "\n")
    return fasta


def _knockout_menu(fasta: Path) -> object:
    from alleleforge.types.edit import EditIntent

    return design(
        _VARIANT,
        reference=ReferenceGenome(fasta, build="hg38"),
        run_offtarget=False,
        intent=EditIntent.KNOCK_OUT,
    )


def _warnings(report: object) -> list[str]:
    return [w for c in report.candidates if c.oligos for w in c.oligos.warnings]


def test_the_fixture_spacer_is_a_hazard_for_exactly_one_enzyme() -> None:
    """Without the asymmetry every assertion below would pass for the wrong reason."""
    assert TYPE_IIS_SITES["BbsI"] in _BBSI_SPACER
    assert TYPE_IIS_SITES["BsmBI"] not in _BBSI_SPACER
    assert TYPE_IIS_SITES["BsaI"] not in _BBSI_SPACER


def test_the_default_vector_reports_the_bbsi_insert_clean(bbsi_fasta: Path) -> None:
    """The defect: right answer for lentiGuide, wrong one for the pX330 user."""
    report = build_report(_knockout_menu(bbsi_fasta), with_oligos=True)
    assert not _warnings(report)


def test_naming_the_users_vector_finds_the_site(bbsi_fasta: Path) -> None:
    report = build_report(_knockout_menu(bbsi_fasta), with_oligos=True, scheme=PX330_BBSI)
    warnings = _warnings(report)
    assert warnings, "the pX330 screen found nothing in an insert that carries GAAGAC"
    assert all(w.startswith("internal-BbsI-site:") for w in warnings), warnings


def test_the_render_names_the_vector_it_screened_against(bbsi_fasta: Path) -> None:
    """A report that flags nothing must still say which enzyme looked."""
    report = build_report(_knockout_menu(bbsi_fasta), with_oligos=True, scheme=PX330_BBSI)
    text = render_pdf(report).decode("latin-1", errors="ignore")
    assert "px330-bbsi" in text and "BbsI" in text
    assert "lentiguide-bsmbi" not in text


def test_a_pegrna_keeps_an_acceptor_that_can_receive_its_extension(tmp_path: Path) -> None:
    """An sgRNA-only vector cannot clone a 3' extension, so it is not applied to one."""
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    fasta = tmp_path / "prime.fa"
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    menu = design(
        "chr2:71:A>C", reference=ReferenceGenome(fasta, build="hg38"), run_offtarget=False
    )
    report = build_report(menu, with_oligos=True, scheme=PX330_BBSI)
    schemes = {c.oligos.scheme.name for c in report.candidates if c.oligos}
    assert schemes == {PEGRNA_GG_BSAI.name}, schemes


def test_every_registered_scheme_resolves_by_its_own_name() -> None:
    for name, scheme in VECTOR_SCHEMES.items():
        assert scheme_by_name(name) is scheme
    assert set(VECTOR_SCHEMES) == {s.name for s in (LENTIGUIDE_BSMBI, PX330_BBSI, PEGRNA_GG_BSAI)}


def test_every_registered_scheme_names_a_screenable_enzyme() -> None:
    """An unscreenable scheme would offer a vector whose hazard cannot be checked."""
    for name, scheme in VECTOR_SCHEMES.items():
        assert scheme.enzyme in TYPE_IIS_SITES, name


def test_an_unknown_scheme_names_the_known_ones() -> None:
    with pytest.raises(ValueError) as excinfo:
        scheme_by_name("px330")
    for name in VECTOR_SCHEMES:
        assert name in str(excinfo.value)


def _design(runner: CliRunner, fasta: Path, *extra: str) -> tuple[int, str]:
    result = runner.invoke(
        app,
        [
            "design",
            _VARIANT,
            "--reference-fasta",
            str(fasta),
            "--intent",
            "knock_out",
            "--no-offtarget",
            *extra,
        ],
    )
    return result.exit_code, result.output + result.stderr


def test_the_cli_can_ask_for_the_users_vector(bbsi_fasta: Path) -> None:
    runner = CliRunner()
    code, default = _design(runner, bbsi_fasta)
    assert code == 0, default
    assert "internal-BbsI-site" not in default

    code, chosen = _design(runner, bbsi_fasta, "--vector-scheme", "px330-bbsi")
    assert code == 0, chosen
    payload = json.loads(chosen)
    flagged = [w for c in payload["candidates"] if c.get("oligos") for w in c["oligos"]["warnings"]]
    assert flagged and all(w.startswith("internal-BbsI-site:") for w in flagged), flagged


def test_the_cli_refuses_an_unknown_vector_by_naming_the_real_ones(bbsi_fasta: Path) -> None:
    code, output = _design(CliRunner(), bbsi_fasta, "--vector-scheme", "px330")
    assert code != 0
    for name in VECTOR_SCHEMES:
        assert name in output
