"""v0.1.0 acceptance suite — the SPEC §16 "definition of done", as executable checks.

Each test maps to one bullet of the specification's acceptance criteria. Where the
per-component test suites prove a unit in isolation, this module proves the
*end-to-end contract a release must honor*: a ClinVar accession flows to a complete,
provenance-stamped, reproducible menu; the unified entry point reaches every
chemistry; the reference-bias finding is reproduced; prime editing unifies all four
axes; and CRISPR-Bench publishes the required tasks with calibration and a working
leaderboard.

Everything runs against the weight-free stub models and synthetic loci, so the
acceptance contract is verified on every CI run with no downloads.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from alleleforge.data.clinvar import ClinicalSignificance, ClinVarDB, ClinVarRecord
from alleleforge.data.gnomad import GnomadDB, PopulationFrequency
from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.candidate import RankedMenu
from alleleforge.types.edit import Chemistry, EditIntent
from alleleforge.types.guide import PAM
from alleleforge.types.offtarget import SiteOrigin
from alleleforge.types.provenance import Provenance
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.types.variant import ClinVarAccession, Variant

FIXED_TS = datetime(2024, 5, 1, tzinfo=UTC)
PAD = "T" * 20
#: A protospacer with an in-window A (ABE-correctable) and an NGG PAM.
ABE_PROTO = "TTTAAACGTTTTTTTTTTTT"

MakeRef = Callable[[str], ReferenceGenome]


@pytest.fixture
def make_reference(tmp_path: Path) -> MakeRef:
    """Return a factory that writes a single-contig FASTA and opens it as a reference."""
    counter = {"n": 0}

    def _make(contig: str) -> ReferenceGenome:
        counter["n"] += 1
        fasta = tmp_path / f"acc{counter['n']}.fa"
        fasta.write_text(f">chr2\n{contig}\n")
        return ReferenceGenome(fasta, build="hg38")

    return _make


def _base_at(reference: ReferenceGenome, zero_based: int) -> str:
    """Return the reference base at a 0-based position on chr2."""
    iv = GenomicInterval(chrom="chr2", start=zero_based, end=zero_based + 1, strand=Strand.PLUS)
    return str(reference.fetch(iv))


def _clinvar_db(reference: ReferenceGenome, *, pos: int, alt: str) -> tuple[ClinVarDB, str]:
    """Build a one-record ClinVar DB whose variant sits at ``pos`` on ``reference``."""
    accession = ClinVarAccession(value="VCV000012345")
    ref = _base_at(reference, pos)
    variant = Variant(chrom="chr2", pos=pos, ref=ref, alt=alt, build="hg38", clinvar=accession)
    record = ClinVarRecord(
        variant=variant,
        accession=accession,
        significance=ClinicalSignificance.PATHOGENIC,
        gene="DEMO",
    )
    return ClinVarDB([record]), accession.value


# --- §16.1: a ClinVar accession flows end to end to a complete menu --------------


def test_clinvar_accession_to_complete_menu(make_reference: MakeRef) -> None:
    reference = make_reference(PAD + ABE_PROTO + "TGG" + PAD)
    clinvar, accession = _clinvar_db(reference, pos=25, alt="G")  # install A->G
    gnomad = GnomadDB(
        [
            PopulationFrequency(
                chrom="chr2",
                pos=8,
                ref="T",
                alt="G",
                overall_af=0.02,
                populations={"afr": 0.09, "nfe": 0.001},
            )
        ]
    )

    menu = design(
        accession,
        reference=reference,
        intent=EditIntent.INSTALL,
        clinvar=clinvar,
        gnomad=gnomad,
        populations=["afr", "nfe"],
        timestamp=FIXED_TS,
    )

    assert isinstance(menu, RankedMenu)
    assert menu.candidates  # the accession resolved and produced a menu
    # Every candidate honors the completeness contract.
    for c in menu.candidates:
        # calibrated efficiency interval, never a bare float
        assert c.efficiency is not None
        lo, hi = c.efficiency.interval
        assert lo <= c.efficiency.value <= hi
        # a predicted outcome distribution
        assert c.outcome is not None and c.outcome.alleles
        # an off-target report, or an explicit reason it lacks one
        assert c.offtarget is not None or any("offtarget" in f or "pam" in f for f in c.flags)
    # complete provenance, re-derivable from config + seed
    assert isinstance(menu.provenance, Provenance)
    assert menu.provenance.alleleforge_version and menu.provenance.seed
    # the routing decision is explained
    assert menu.rationale is not None and "Routing" in menu.rationale


# --- §16.1: the unified entry point reaches every eligible chemistry -------------


def test_every_chemistry_reachable_through_one_entry_point(make_reference: MakeRef) -> None:
    # base editing: an SNV install into an ABE window
    abe = make_reference(PAD + ABE_PROTO + "TGG" + PAD)
    base_menu = design(f"chr2:26:{_base_at(abe, 25)}>G", reference=abe, intent=EditIntent.INSTALL)

    # prime editing: an install at a locus with a pegRNA PAM and a PE3b ngRNA PAM
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    prime_ref = make_reference("".join(seq))
    prime_menu = design(
        f"chr2:71:{_base_at(prime_ref, 70)}>C", reference=prime_ref, intent=EditIntent.INSTALL
    )

    # nuclease: a knock-out routes to SpCas9 only
    nuc = make_reference(PAD + "ACGTAACGTTACGTAACGTT" + "TGG" + PAD)
    nuc_menu = design("chr2:26:A>G", reference=nuc, intent=EditIntent.KNOCK_OUT)

    reached = (
        {c.chemistry for c in base_menu.candidates}
        | {c.chemistry for c in prime_menu.candidates}
        | {c.chemistry for c in nuc_menu.candidates}
    )
    assert {Chemistry.BASE_ABE, Chemistry.PRIME, Chemistry.CAS9_NUCLEASE} <= reached


# --- §16: reproducible from config + seed ----------------------------------------


def test_run_is_reproducible_from_seed(make_reference: MakeRef) -> None:
    reference = make_reference(PAD + ABE_PROTO + "TGG" + PAD)
    clinvar, accession = _clinvar_db(reference, pos=25, alt="G")
    kwargs = dict(
        reference=reference, intent=EditIntent.INSTALL, clinvar=clinvar, timestamp=FIXED_TS
    )

    first = design(accession, **kwargs)  # type: ignore[arg-type]
    second = design(accession, **kwargs)  # type: ignore[arg-type]
    assert first.model_dump_json() == second.model_dump_json()


# --- §16.2: the reference-bias / rs114518452 case is reproduced ------------------


def test_reference_bias_case_reproduced(make_reference: MakeRef) -> None:
    spacer = "GACCATGCAACCTTGAACGT"  # no internal NRG PAM: it never self-matches
    pad = "T" * 10
    reference = make_reference(pad + spacer + "CGT" + pad)  # reference: no NGG after protospacer
    ngg = PAM(pattern="NGG")

    # A reference-only scan is blind to the off-target.
    assert search(spacer, ngg, reference=reference).n_sites == 0

    # A population allele (rs114518452-like, AFR-enriched) creates a de-novo NGG PAM.
    allele = PopulationFrequency(
        chrom="chr2",
        pos=32,
        ref="T",
        alt="G",
        overall_af=0.03,
        populations={"afr": 0.105, "amr": 0.012, "eas": 0.0, "nfe": 0.001, "sas": 0.0},
    )
    report = search(spacer, ngg, reference=reference, gnomad=GnomadDB([allele]))
    assert report.n_sites == 1
    site = report.sites[0]
    assert site.origin is SiteOrigin.POPULATION
    assert site.score >= 0.20  # high-CFD off-target
    # the risk is ancestry-stratified, concentrated in African-ancestry genomes
    assert site.ancestries["afr"] == max(site.ancestries.values())
    assert report.ancestry_stratification() and report.worst_ancestry() is not None


# --- §16.3: prime editing unifies all four axes ---------------------------------


def test_prime_unifies_all_four_axes(make_reference: MakeRef) -> None:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    reference = make_reference("".join(seq))
    menu = design(
        f"chr2:71:{_base_at(reference, 70)}>C",
        reference=reference,
        intent=EditIntent.INSTALL,
        chemistries=[Chemistry.PRIME],
        timestamp=FIXED_TS,
    )
    assert menu.candidates
    top = menu.best
    assert top is not None and top.chemistry is Chemistry.PRIME
    # axis 1: variant input drove a concrete pegRNA design
    assert top.pegrna is not None and top.pegrna.spacer.sequence
    # axis 2: ML efficiency with calibrated uncertainty + an honest OOD flag
    assert top.efficiency is not None
    assert isinstance(top.efficiency.in_distribution, bool)
    # axis 3: intended-vs-byproduct outcome distribution
    assert top.outcome is not None and any(a.is_intended for a in top.outcome.alleles)
    # axis 4: a population-aware off-target report (or an explicit reason)
    assert top.offtarget is not None or any("offtarget" in f or "pam" in f for f in top.flags)


# --- §16.4: CRISPR-Bench publishes the required tasks ----------------------------


def test_crispr_bench_publishes_required_tasks() -> None:
    from alleleforge.benchmark import (
        TASKS,
        Leaderboard,
        ModelInfo,
        Submission,
        build_baseline,
        get_task,
        load_split,
        run_benchmark,
    )

    required = {"cas9-efficiency", "pe-efficiency", "offtarget-classification"}
    assert required <= set(TASKS)

    results = []
    for name in sorted(required):
        task = get_task(name)
        assert "ece" in task.metrics  # calibration required on every task
        split, dataset = load_split(name)  # frozen split, integrity-verified on read
        assert split.test
        baseline = build_baseline(task, split, dataset)
        result = run_benchmark(baseline, task, split=split, dataset=dataset, timestamp=FIXED_TS)
        assert result.verify_signature()  # signed, provenance-stamped
        results.append(result)

    # a working leaderboard accepts the carded submission and renders
    board = Leaderboard()
    board.add(
        Submission(
            submitter="alleleforge",
            model=ModelInfo(
                name="crispr-bench-baseline", version="1.0", license="MIT", citation="AlleleForge"
            ),
            results=tuple(results),
            submitted_at=FIXED_TS,
        )
    )
    assert set(board.tasks) == required
    assert "CRISPR-Bench Leaderboard" in board.render_markdown()
