"""Tests for the optional Cas-OFFinder cross-check adapter."""

from __future__ import annotations

from pathlib import Path

from alleleforge.offtarget.cas_offinder_adapter import CasOffinderAdapter
from alleleforge.types.guide import PAM
from alleleforge.types.offtarget import OffTargetReport, OffTargetSite, ScoreMethod, SiteOrigin
from alleleforge.types.sequence import GenomicInterval, Strand

_FIXTURES = Path(__file__).parent / "fixtures"
_SPACER = "GACCATGCAACCTTGAACGT"


def _site(
    start: int, origin: SiteOrigin, strand: Strand = Strand.PLUS
) -> OffTargetSite:
    return OffTargetSite(
        locus=GenomicInterval(chrom="chr2", start=start, end=start + 20, strand=strand),
        mismatches=1,
        score=0.5,
        score_method=ScoreMethod.CFD,
        origin=origin,
        causal_allele="chr2:1:A>G" if origin is not SiteOrigin.REFERENCE else None,
    )


def _report(*sites: OffTargetSite) -> OffTargetReport:
    return OffTargetReport(spacer="A" * 20, pam="NGG", sites=sites)


def test_available_reflects_path() -> None:
    assert CasOffinderAdapter(binary="definitely-not-a-real-binary-xyz").available() is False


def test_reference_loci_excludes_population_sites() -> None:
    report = _report(_site(10, SiteOrigin.REFERENCE), _site(50, SiteOrigin.POPULATION))
    loci = CasOffinderAdapter.reference_loci(report)
    assert loci == {("chr2", 10, Strand.PLUS)}  # population site has no Cas-OFFinder counterpart


def test_agreement_has_no_disagreements() -> None:
    report = _report(_site(10, SiteOrigin.REFERENCE))
    diff = CasOffinderAdapter().disagreements(report, {("chr2", 10, Strand.PLUS)})
    assert diff["only_alleleforge"] == set()
    assert diff["only_cas_offinder"] == set()


def test_minus_strand_locus_reconciled_to_whole_match_leftmost() -> None:
    # AlleleForge's minus-strand locus records the protospacer start (PAM excluded);
    # Cas-OFFinder reports the whole protospacer+PAM leftmost, which on the minus
    # strand is pam_len (3 for NGG) below it. reference_loci must shift so a site
    # both engines agree on is NOT flagged as a disagreement.
    report = _report(_site(1000, SiteOrigin.REFERENCE, strand=Strand.MINUS))
    assert CasOffinderAdapter.reference_loci(report) == {("chr2", 997, Strand.MINUS)}
    diff = CasOffinderAdapter().disagreements(report, {("chr2", 997, Strand.MINUS)})
    assert diff["only_alleleforge"] == set()
    assert diff["only_cas_offinder"] == set()


def test_disagreements_flagged_both_ways() -> None:
    report = _report(_site(10, SiteOrigin.REFERENCE))
    diff = CasOffinderAdapter().disagreements(report, {("chr2", 99, Strand.PLUS)})
    assert diff["only_alleleforge"] == {("chr2", 10, Strand.PLUS)}
    assert diff["only_cas_offinder"] == {("chr2", 99, Strand.PLUS)}


# --- input deck + output parsing (recorded fixtures, no binary) ------------------


def test_format_input_deck() -> None:
    deck = CasOffinderAdapter.format_input("/genomes/hg38.fa", _SPACER, PAM(pattern="NGG"), 4)
    lines = deck.splitlines()
    assert lines[0] == "/genomes/hg38.fa"
    assert lines[1] == "N" * 20 + "NGG"  # spacer Ns + PAM
    assert lines[2] == _SPACER + "NNN 4"  # spacer + PAM-as-N + budget


def test_parse_output_legacy_format() -> None:
    loci = CasOffinderAdapter.parse_output((_FIXTURES / "cas_offinder_legacy.txt").read_text())
    assert loci == {
        ("chr2", 10, Strand.PLUS),
        ("chr2", 512, Strand.PLUS),
        ("chr5", 8841, Strand.MINUS),
    }


def test_parse_output_bulge_format_with_header() -> None:
    loci = CasOffinderAdapter.parse_output((_FIXTURES / "cas_offinder_bulge.txt").read_text())
    assert loci == {
        ("chr2", 10, Strand.PLUS),
        ("chr2", 512, Strand.PLUS),
        ("chr7", 1200, Strand.PLUS),
    }


def test_parse_output_ignores_blank_and_malformed_lines() -> None:
    assert CasOffinderAdapter.parse_output("\n#header only\nfoo bar\n") == set()


def test_parse_output_ignores_unknown_direction() -> None:
    # A 6-column row whose direction is neither + nor - is skipped, not crashed on.
    row = "GACCATGCAACCTTGAACGTNGG\tchr2\t10\tGACCATGCAACCTTGAACGTAGG\t?\t0"
    assert CasOffinderAdapter.parse_output(row) == set()


def test_run_with_injected_runner_parses_loci() -> None:
    # The orchestration (write deck -> run -> parse) is driven without the binary.
    captured: dict[str, str] = {}

    def fake_runner(input_path: str) -> str:
        captured["deck"] = Path(input_path).read_text()
        return (_FIXTURES / "cas_offinder_legacy.txt").read_text()

    loci = CasOffinderAdapter().run(
        "/genomes/hg38.fa", _SPACER, PAM(pattern="NGG"), runner=fake_runner
    )
    assert ("chr5", 8841, Strand.MINUS) in loci
    assert captured["deck"].splitlines()[1] == "N" * 20 + "NGG"


def test_run_raises_without_binary_or_runner() -> None:
    adapter = CasOffinderAdapter(binary="definitely-not-a-real-binary-xyz")
    try:
        adapter.run("/genomes/hg38.fa", _SPACER, PAM(pattern="NGG"))
    except RuntimeError as exc:
        assert "not on PATH" in str(exc)
    else:  # pragma: no cover - the call must raise
        raise AssertionError("expected RuntimeError when the binary is absent")
