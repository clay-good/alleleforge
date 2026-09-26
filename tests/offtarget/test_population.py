"""Tests for population-variant off-target augmentation."""

from __future__ import annotations

from collections.abc import Callable

from alleleforge.data.gnomad import PopulationFrequency
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.population import enumerate_patient_sites, enumerate_population_sites
from alleleforge.types.guide import PAM
from alleleforge.types.offtarget import SiteOrigin
from alleleforge.types.variant import Variant

from .conftest import PAD, SPACER

NRG = PAM(pattern="NRG")
MakeRef = Callable[[dict[str, str]], ReferenceGenome]


def test_nomination_scores_dna_bulge_hits_like_reporting() -> None:
    # Nomination and reporting must score a hit the same way, or a population hit can
    # be judged "not strengthening" (and lose its ancestry attribution) by a number
    # the report never shows. A DNA bulge collapses the target but leaves both strings
    # 20 nt, so the CFD fallback only fires when the bulge status is passed through —
    # nomination must pass `bulged=` exactly as engine._scores does for reporting.
    from alleleforge.offtarget._search import Hit
    from alleleforge.offtarget.population import _reference_best
    from alleleforge.offtarget.scoring import CfdScorer
    from alleleforge.types.sequence import Strand

    sp = "GACGCTAGACGATCGATCGA"
    tg = "GACGCTAGACGATCGATCGT"  # one PAM-proximal mismatch
    published = CfdScorer().score(sp, tg, "AGG")
    approx = CfdScorer(approximate=True).score(sp, tg, "AGG")
    assert published != approx  # the two paths give different numbers here
    hit = Hit(
        chrom="chr2",
        start=100,
        end=120,
        strand=Strand.PLUS,
        pam_sequence="AGG",
        aligned_spacer=sp,
        aligned_target=tg,
        mismatches=1,
        dna_bulges=1,
        rna_bulges=0,
    )
    nominated = _reference_best([hit], CfdScorer())[(Strand.PLUS, 100, 120)][0]
    assert nominated == approx  # the bulge-collapsed approximation, matching reporting
    assert nominated != published


def test_touches_uses_variant_span_not_just_anchor() -> None:
    # A multi-base deletion/MNV must be attributed to a hit when *any* of its
    # changed bases reach the hit's protospacer+PAM window — testing only the
    # anchor `pos` drops a hit whose overlap is at a non-anchor base (a false
    # negative in the safety-critical nomination path). SNV behavior is unchanged.
    from alleleforge.offtarget._search import Hit
    from alleleforge.offtarget.population import _touches
    from alleleforge.types.sequence import Strand

    hit = Hit(
        chrom="chr1",
        start=104,
        end=124,
        strand=Strand.PLUS,
        pam_sequence="TGG",
        aligned_spacer="A" * 20,
        aligned_target="A" * 20,
        mismatches=0,
        dna_bulges=0,
        rna_bulges=0,
    )  # window with pam_len=3 is [101, 127)
    # anchor pos=100 is outside the window, but the 3-base span [100, 103) reaches
    # bases 101/102 inside it -> must be attributed.
    assert _touches(hit, 100, 3, 3) is True
    assert _touches(hit, 100, 1, 3) is False  # an SNV at 100 really is outside
    # SNV equivalence with the previous point test at the window's edges.
    assert _touches(hit, 101, 1, 3) is True  # 101 == hit.start - pam_len (inclusive)
    assert _touches(hit, 126, 1, 3) is True  # 126 < hit.end + pam_len (127)
    assert _touches(hit, 127, 1, 3) is False  # 127 == hit.end + pam_len (exclusive)


def test_de_novo_pam_creation(make_reference: MakeRef) -> None:
    # Reference has no PAM (CGT); a T->G at the PAM's 3rd base creates CGG.
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    pf = PopulationFrequency(
        chrom="chr2",
        pos=32,
        ref="T",
        alt="G",
        overall_af=0.05,
        populations={"afr": 0.10, "nfe": 0.01},
    )
    sites = enumerate_population_sites(SPACER, NRG, reference=ref, variants=[pf], maf=0.001)
    assert len(sites) == 1
    hit, prov = sites[0]
    assert (hit.start, hit.end) == (10, 30)
    assert hit.mismatches == 0
    assert prov.origin is SiteOrigin.POPULATION
    assert prov.causal_allele == "chr2:32:T>G"
    assert prov.populations == ("afr", "nfe")
    assert prov.frequency == 0.10


def test_maf_filter_excludes_rare_variant(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    pf = PopulationFrequency(
        chrom="chr2",
        pos=32,
        ref="T",
        alt="G",
        overall_af=0.0001,
        populations={"afr": 0.0001},
    )
    assert enumerate_population_sites(SPACER, NRG, reference=ref, variants=[pf], maf=0.001) == []


def test_variant_that_creates_nothing_is_silent(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    # A->G well away from any protospacer/PAM: creates no site.
    pf = PopulationFrequency(
        chrom="chr2", pos=2, ref="T", alt="G", overall_af=0.2, populations={"afr": 0.2}
    )
    assert enumerate_population_sites(SPACER, NRG, reference=ref, variants=[pf], maf=0.001) == []


def test_variant_strengthens_existing_site(make_reference: MakeRef) -> None:
    # Reference site has a single mismatch at protospacer position 5; the variant
    # restores it, dropping the edit count -> a strengthened population site.
    mutated = SPACER[:5] + ("A" if SPACER[5] != "A" else "C") + SPACER[6:]
    ref = make_reference({"chr2": PAD + mutated + "TGG" + PAD})
    pf = PopulationFrequency(
        chrom="chr2",
        pos=15,
        ref=mutated[5],
        alt=SPACER[5],
        overall_af=0.05,
        populations={"eas": 0.05},
    )
    sites = enumerate_population_sites(SPACER, NRG, reference=ref, variants=[pf], maf=0.001)
    assert len(sites) == 1
    hit, _ = sites[0]
    assert hit.mismatches == 0


def test_pam_upgrade_strengthens_at_unchanged_edit_count(make_reference: MakeRef) -> None:
    # A perfect protospacer sits 5' of a weak NAG PAM (CFD ~0.26); a minor allele
    # flips the PAM's middle base A->G, making canonical NGG (CFD 1.0) without
    # touching the protospacer. The edit count is unchanged, so the old edit-count
    # gate dropped this site; the score-based gate nominates the strengthened PAM.
    ref = make_reference({"chr2": PAD + SPACER + "CAG" + PAD})  # NAG PAM after the spacer
    pf = PopulationFrequency(
        chrom="chr2",
        pos=31,  # the 'A' of CAG, 3' of the spacer at [10, 30)
        ref="A",
        alt="G",
        overall_af=0.03,
        populations={"afr": 0.08, "nfe": 0.001},
    )
    sites = enumerate_population_sites(SPACER, NRG, reference=ref, variants=[pf], maf=0.001)
    assert len(sites) == 1
    hit, prov = sites[0]
    assert (hit.start, hit.end) == (10, 30)
    assert hit.mismatches == 0
    assert hit.pam_sequence == "CGG"  # the upgraded, canonical PAM
    assert prov.origin is SiteOrigin.POPULATION
    assert prov.causal_allele == "chr2:31:A>G"
    assert "afr" in prov.populations


def test_pam_downgrade_is_not_nominated(make_reference: MakeRef) -> None:
    # The mirror of the upgrade: a canonical NGG PAM downgraded to weak NAG lowers
    # the CFD at an unchanged edit count. That is a *weakening*, not a strengthening,
    # so the score-directional gate correctly reports nothing.
    ref = make_reference({"chr2": PAD + SPACER + "CGG" + PAD})  # canonical NGG PAM
    pf = PopulationFrequency(
        chrom="chr2", pos=31, ref="G", alt="A", overall_af=0.05, populations={"afr": 0.05}
    )
    assert enumerate_population_sites(SPACER, NRG, reference=ref, variants=[pf], maf=0.001) == []


def test_absent_contig_is_skipped(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    pf = PopulationFrequency(
        chrom="chrX", pos=5, ref="A", alt="G", overall_af=0.2, populations={"afr": 0.2}
    )
    assert enumerate_population_sites(SPACER, NRG, reference=ref, variants=[pf], maf=0.001) == []


def test_ref_mismatch_is_skipped(make_reference: MakeRef) -> None:
    # The variant asserts ref 'A' but the build has 'T' here -> skipped safely.
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    pf = PopulationFrequency(
        chrom="chr2", pos=32, ref="A", alt="G", overall_af=0.2, populations={"afr": 0.2}
    )
    assert enumerate_population_sites(SPACER, NRG, reference=ref, variants=[pf], maf=0.001) == []


def test_patient_sites_tagged_patient(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    var = Variant(chrom="chr2", pos=32, ref="T", alt="G")
    sites = enumerate_patient_sites(SPACER, NRG, reference=ref, variants=[var])
    assert len(sites) == 1
    _, prov = sites[0]
    assert prov.origin is SiteOrigin.PATIENT
    assert prov.frequency is None


def test_deletion_places_downstream_hit_at_correct_locus(make_reference: MakeRef) -> None:
    # The reference carries an extra base inside the protospacer (a DNA-bulge site
    # at 4 nt... here 0 mm via the bulge); a deletion removes it, restoring a clean
    # 0-mismatch protospacer. The nominated hit must be placed at its TRUE genomic
    # locus [10, 31) — spanning the deleted base — not shifted by the deletion.
    contig = PAD + SPACER[:10] + "A" + SPACER[10:] + "AGG" + PAD
    ref = make_reference({"chr2": contig})
    # Delete the inserted 'A' at genomic 20 (anchored at 19: 'A'(SPACER[9]) + 'A').
    pf = PopulationFrequency(
        chrom="chr2", pos=19, ref="AA", alt="A", overall_af=0.2, populations={"afr": 0.2}
    )
    hits = [h for h, _ in enumerate_population_sites(SPACER, NRG, reference=ref, variants=[pf])]
    # The restored ungapped protospacer (its PAM is the "AGG") is placed at
    # [10, 31), spanning the deleted base — not shifted to end 30.
    agg = [h for h in hits if h.pam_sequence == "AGG" and h.rna_bulges == 0]
    assert len(agg) == 1
    assert (agg[0].start, agg[0].end, agg[0].mismatches) == (10, 31, 0)


def test_insertion_places_downstream_hit_at_correct_locus(make_reference: MakeRef) -> None:
    # The reference is missing one protospacer base (an RNA-bulge site); an
    # insertion restores it, creating a clean protospacer that straddles the
    # insertion. The hit must be reported at [10, 29) — the true genomic span,
    # one shorter than the 20-nt protospacer because of the inserted base.
    contig = PAD + SPACER[:10] + SPACER[11:] + "AGG" + PAD
    ref = make_reference({"chr2": contig})
    # Insert SPACER[10] ('C') back between genomic 19 and 20 (anchored at 19).
    pf = PopulationFrequency(
        chrom="chr2",
        pos=19,
        ref=SPACER[9],
        alt=SPACER[9] + SPACER[10],
        overall_af=0.2,
        populations={"afr": 0.2},
    )
    hits = [h for h, _ in enumerate_population_sites(SPACER, NRG, reference=ref, variants=[pf])]
    # The restored ungapped protospacer straddles the insertion: its genomic span
    # [10, 29) is one shorter than the 20-nt protospacer, not the naive end 30.
    agg = [h for h in hits if h.pam_sequence == "AGG" and h.rna_bulges == 0]
    assert len(agg) == 1
    assert (agg[0].start, agg[0].end, agg[0].mismatches) == (10, 29, 0)


# -- the reference baseline an alt hit has to beat -----------------------------
#
# `_reference_best` establishes the *strongest* reference hit per placement, and
# `_strengthens` nominates an alt hit only when it beats that. Both were exercised only
# through fixtures holding **one** reference hit per placement, so `prev` was always
# `None` and the aggregation below never ran: swapping its `max` for `min` (or its `min`
# for `max`) changed nothing in 2,087 tests. Understating the baseline is the direction
# that matters — every alt hit then looks like a strengthening, and the population pass
# over-attributes sites to the variant.


def _hit(
    *,
    score_target: str,
    mismatches: int,
    start: int = 100,
    dna_bulges: int = 0,
    rna_bulges: int = 0,
    pam: str = "AGG",
):
    from alleleforge.offtarget._search import Hit
    from alleleforge.types.sequence import Strand

    return Hit(
        chrom="chr2",
        start=start,
        end=start + 20,
        strand=Strand.PLUS,
        pam_sequence=pam,
        aligned_spacer="GACGCTAGACGATCGATCGA",
        aligned_target=score_target,
        mismatches=mismatches,
        dna_bulges=dna_bulges,
        rna_bulges=rna_bulges,
    )


class _RecordingScorer:
    """Returns a score keyed by target, and records every ``bulged`` it was passed."""

    name = "recording"
    matrix = "recording"

    def __init__(self, scores: dict[str, float]) -> None:
        self.scores = scores
        self.bulged_seen: list[bool] = []
        self.calls = 0

    @property
    def method(self):  # type: ignore[no-untyped-def]
        from alleleforge.types.offtarget import ScoreMethod

        return ScoreMethod.CFD

    def score(
        self, spacer: str, protospacer: str, pam_sequence: str, *, bulged: bool = False
    ) -> float:
        self.calls += 1
        self.bulged_seen.append(bulged)
        return self.scores[protospacer]


def test_the_reference_baseline_keeps_the_strongest_hit_at_a_placement() -> None:
    """Two reference hits at one placement: the max score and the fewest edits.

    A fixture with a single hit cannot measure an aggregator — `prev` stays `None` and
    the `max`/`min` are never evaluated.
    """
    from alleleforge.offtarget.population import _reference_best
    from alleleforge.types.sequence import Strand

    weak = _hit(score_target="T" * 20, mismatches=4)
    strong = _hit(score_target="C" * 20, mismatches=1)
    scorer = _RecordingScorer({"T" * 20: 0.10, "C" * 20: 0.90})

    best = _reference_best([weak, strong], scorer)[(Strand.PLUS, 100, 120)]
    assert best == (0.90, 1), "the baseline must be the strongest hit, not the last one"

    # Order must not matter, which a single-hit fixture also cannot check.
    reversed_best = _reference_best([strong, weak], scorer)[(Strand.PLUS, 100, 120)]
    assert reversed_best == (0.90, 1)


def test_the_reference_baseline_is_per_placement() -> None:
    """The aggregation is keyed, so two placements must not collapse into one."""
    from alleleforge.offtarget.population import _reference_best
    from alleleforge.types.sequence import Strand

    here = _hit(score_target="T" * 20, mismatches=4, start=100)
    elsewhere = _hit(score_target="C" * 20, mismatches=1, start=500)
    scorer = _RecordingScorer({"T" * 20: 0.10, "C" * 20: 0.90})

    best = _reference_best([here, elsewhere], scorer)
    assert best[(Strand.PLUS, 100, 120)] == (0.10, 4)
    assert best[(Strand.PLUS, 500, 520)] == (0.90, 1)


def test_a_bulge_free_reference_hit_is_not_scored_as_bulged() -> None:
    """`bulged` comes from the hit's own counts: `> 0`, not `>= 0`.

    Relaxed, every reference hit is scored off the bulge fallback, which lowers the
    baseline the alt hit has to beat and over-attributes sites to the variant.
    """
    from alleleforge.offtarget.population import _reference_best

    scorer = _RecordingScorer({"T" * 20: 0.10})
    _reference_best([_hit(score_target="T" * 20, mismatches=4)], scorer)
    assert scorer.bulged_seen == [False]

    bulged = _RecordingScorer({"T" * 20: 0.10})
    _reference_best([_hit(score_target="T" * 20, mismatches=3, dna_bulges=1)], bulged)
    assert bulged.bulged_seen == [True]


# -- "more dangerous than the reference" --------------------------------------


def test_an_alt_hit_matching_the_reference_exactly_is_not_a_strengthening() -> None:
    """The docstring says *strictly* higher and *strictly* fewer, so pin the equality.

    Relaxed to `>=`, an alt hit identical to the reference hit at that placement is
    attributed to the variant — the population pass then reports sites the variant did
    not create or strengthen, with an ancestry attached to each.
    """
    from alleleforge.offtarget.population import _strengthens

    scorer = _RecordingScorer({"T" * 20: 0.50})
    same = _hit(score_target="T" * 20, mismatches=2)
    assert _strengthens(same, (0.50, 2), scorer) is False


def test_an_alt_hit_beating_the_reference_on_either_measure_is_a_strengthening() -> None:
    """The union gate: a higher score, or fewer edits, each on its own."""
    from alleleforge.offtarget.population import _strengthens

    scorer = _RecordingScorer({"T" * 20: 0.60})
    higher_score = _hit(score_target="T" * 20, mismatches=2)
    assert _strengthens(higher_score, (0.50, 2), scorer) is True

    # Same score, one fewer edit — the case the bulge-blind score alone would miss.
    scorer = _RecordingScorer({"T" * 20: 0.50})
    fewer_edits = _hit(score_target="T" * 20, mismatches=1)
    assert _strengthens(fewer_edits, (0.50, 2), scorer) is True


def test_a_created_hit_needs_no_reference_to_beat() -> None:
    """No reference hit at the placement means the variant created the site."""
    from alleleforge.offtarget.population import _strengthens

    scorer = _RecordingScorer({"T" * 20: 0.01})
    assert _strengthens(_hit(score_target="T" * 20, mismatches=4), None, scorer) is True


def test_a_bulge_free_alt_hit_is_not_scored_as_bulged() -> None:
    """The same `> 0` on the alt side, where the penalty *drops* a real site.

    This is the dangerous direction of the pair: an alt hit scored off the bulge
    fallback scores lower, fails the gate, and the population site disappears.
    """
    from alleleforge.offtarget.population import _strengthens

    scorer = _RecordingScorer({"T" * 20: 0.60})
    _strengthens(_hit(score_target="T" * 20, mismatches=2), (0.50, 2), scorer)
    assert scorer.bulged_seen == [False]


# -- a supplied scorer is the scorer that runs ---------------------------------


def test_the_patient_pass_uses_the_scorer_it_was_given(make_reference: MakeRef) -> None:
    """`scorer if scorer is not None else CfdScorer()` — inverted, the argument is dropped.

    The patient pass then scores a personal off-target site with the default matrix
    however the caller configured the run, and nothing says so: the sites still appear,
    tagged PATIENT, carrying numbers from a scorer nobody asked for.
    `enumerate_population_sites` has the identical line and is checked here too, because a
    guard holding on one of two parallel call sites is a shape this repository keeps
    finding.

    The window holds an exact match with an NRG PAM, so reference hits exist and are
    scored. A fixture whose site the variant *creates* cannot measure this at all:
    `_strengthens` returns early on `prior is None` and never reaches a scorer.
    """
    contig = PAD + SPACER + "AGG" + PAD
    ref = make_reference({"chr2": contig})
    pos0 = len(PAD) + len(SPACER) + 3  # just past the PAM, still inside the scan window
    base = contig[pos0]
    alt = "A" if base != "A" else "G"

    class _Sentinel:
        name = "sentinel"
        matrix = "sentinel-matrix"
        calls = 0

        @property
        def method(self):  # type: ignore[no-untyped-def]
            from alleleforge.types.offtarget import ScoreMethod

            return ScoreMethod.CFD

        def score(
            self, spacer: str, protospacer: str, pam_sequence: str, *, bulged: bool = False
        ) -> float:
            type(self).calls += 1
            return 1.0

    sentinel = _Sentinel()
    var = Variant(chrom="chr2", pos=pos0 + 1, ref=base, alt=alt)
    enumerate_patient_sites(SPACER, NRG, reference=ref, variants=[var], scorer=sentinel)
    assert _Sentinel.calls, "the patient pass ignored the scorer it was handed"

    _Sentinel.calls = 0
    pf = PopulationFrequency(
        chrom="chr2", pos=pos0 + 1, ref=base, alt=alt, overall_af=0.2, populations={"afr": 0.2}
    )
    enumerate_population_sites(
        SPACER, NRG, reference=ref, variants=[pf], maf=0.001, scorer=sentinel
    )
    assert _Sentinel.calls, "the population pass ignored the scorer it was handed"
