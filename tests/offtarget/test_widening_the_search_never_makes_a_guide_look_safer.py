"""Widening a budget must never reduce the reported risk.

Every knob on `search()` trades runtime for thoroughness: more mismatches, bulges allowed,
a lower reporting cut-off. Each of those can only *find* more, so no result derived from a
wider search may look better than one from a narrower search of the same spacer. If it
ever does, a user who paid for a more thorough scan is told their guide is safer than the
cheap scan said — the worst direction for this failure to run in.

Nothing tested it. This project has already shipped one monotonicity violation on the
safety axis (adding a benign ancestry-tagged site *raised* a candidate's safety score), so
the class is not hypothetical.

One property has to be stated carefully, and getting it wrong is instructive: "every locus
found narrowly is still found widely" is **false**, and correctly so. Allowing a DNA bulge
let the engine realign a 2-mismatch hit at `chr1:596-616` as a 0-mismatch, 1-bulge hit at
`chr1:595-616` — the same site, one base longer, scoring 1.000 instead of 0.517. The
engine keeps the best-scoring alignment per site, so the *interval* moved. The property
that actually matters is coverage: every narrowly-found site is overlapped by a widely-found
site scoring at least as high.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM
from alleleforge.types.offtarget import OffTargetReport, OffTargetSite

NGG = PAM(pattern="NGG")


def _mutate(spacer: str, k: int, seed: int) -> str:
    rng = random.Random(seed)
    bases = list(spacer)
    for position in rng.sample(range(len(bases)), k):
        bases[position] = rng.choice([b for b in "ACGT" if b != bases[position]])
    return "".join(bases)


@pytest.fixture
def case(tmp_path: Path) -> tuple[ReferenceGenome, str]:
    """A spacer with a perfect site and five progressively worse ones, each PAM-adjacent."""
    rng = random.Random(5)
    spacer = "".join(rng.choice("ACGT") for _ in range(20))
    pad = lambda n: "".join(rng.choice("ACGT") for _ in range(n))  # noqa: E731
    parts = [pad(200), spacer, "AGG", pad(200)]
    for k in (1, 2, 3, 4, 5):
        parts += [_mutate(spacer, k, k), "TGG", pad(150)]
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr1\n" + "".join(parts) + "\n")
    return ReferenceGenome(fasta, build="hg38"), spacer


def _run(reference: ReferenceGenome, spacer: str, **kwargs: object) -> OffTargetReport:
    return search(spacer, NGG, reference=reference, cfd_threshold=0.0, mit_threshold=0.0, **kwargs)


def _overlaps(a: OffTargetSite, b: OffTargetSite) -> bool:
    return (
        a.locus.chrom == b.locus.chrom
        and a.locus.start < b.locus.end
        and b.locus.start < a.locus.end
    )


def test_more_mismatches_never_loses_a_site(case: tuple[ReferenceGenome, str]) -> None:
    reference, spacer = case
    previous: set[str] = set()
    for budget in range(5):
        found = {
            str(s.locus)
            for s in _run(reference, spacer, mismatches=budget, dna_bulges=0, rna_bulges=0).sites
        }
        assert previous <= found, f"raising the budget to {budget} lost {sorted(previous - found)}"
        previous = found


def test_a_lower_cut_off_never_loses_a_site(case: tuple[ReferenceGenome, str]) -> None:
    reference, spacer = case
    previous: set[str] = set()
    for cut_off in (0.9, 0.6, 0.3, 0.1, 0.0):
        report = search(
            spacer,
            NGG,
            reference=reference,
            mismatches=5,
            dna_bulges=0,
            rna_bulges=0,
            cfd_threshold=cut_off,
            mit_threshold=1.01,
        )
        found = {str(s.locus) for s in report.sites}
        assert previous <= found, f"lowering to {cut_off} lost {sorted(previous - found)}"
        previous = found


def test_allowing_bulges_covers_every_ungapped_site(case: tuple[ReferenceGenome, str]) -> None:
    """Coverage, not identity: a realigned site legitimately reports a different interval."""
    reference, spacer = case
    narrow = _run(reference, spacer, mismatches=4, dna_bulges=0, rna_bulges=0)
    wide = _run(reference, spacer, mismatches=4, dna_bulges=1, rna_bulges=1)
    assert narrow.sites, "the fixture must nominate something"
    for site in narrow.sites:
        covering = [w.score for w in wide.sites if _overlaps(site, w)]
        assert covering, f"{site.locus} vanished when bulges were allowed"
        assert max(covering) >= site.score - 1e-9, (
            f"{site.locus} scored {site.score} ungapped and at most {max(covering)} with "
            "bulges — a more thorough scan reported less risk"
        )


def test_a_wider_search_never_reports_a_better_guide(case: tuple[ReferenceGenome, str]) -> None:
    reference, spacer = case
    narrow = _run(reference, spacer, mismatches=4, dna_bulges=0, rna_bulges=0)
    wide = _run(reference, spacer, mismatches=4, dna_bulges=1, rna_bulges=1)
    assert wide.specificity_score() <= narrow.specificity_score() + 1e-12
    assert wide.worst_score() >= narrow.worst_score() - 1e-12
