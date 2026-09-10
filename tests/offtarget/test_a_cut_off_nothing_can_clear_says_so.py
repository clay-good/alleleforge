"""A refusal that states a stricter contract than it applies, and the silence behind it.

`reject_non_finite`'s message read "a threshold must be a finite fraction in **[0, 1]**"
and the check enforced only the finite half. `search(cfd_threshold=2)` was accepted and
returned `0 site(s)` — the most reassuring output this system can produce, from a cut-off no
score can reach. A reader who checks their input against a sentence that strict, and passes,
concludes the input was fine; a message stricter than the code is worse than no message.

**The range is not enforced, on purpose.** Nomination is an OR of a CFD and an MIT
threshold and scores live in `[0, 1]`, so a value above 1 is the only way to say "nominate
on CFD alone" — this repository's own tests use `mit_threshold=1.1` for exactly that, and
the first version of this fix broke five of them. The bug was never the acceptance; it was
that an unreachable cut-off moved the numbers in silence.

So: the message says what is enforced, and the report says when a cut-off is outside the
range any score can reach. The CLI clamps to `[0, 1]` and never gets here; a Python caller
and an API client do.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget._bounds import reject_non_finite
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM
from alleleforge.types.offtarget import headline_notes

_SPACER = "ATATATATATATATATATAT"


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    path = tmp_path / "r.fa"
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    path.write_text(">chr2\n" + "".join(seq) + "\n")
    return ReferenceGenome(path, build="hg38")


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_a_non_finite_threshold_is_still_refused(value: float) -> None:
    with pytest.raises(ValueError, match="finite number"):
        reject_non_finite(cfd_threshold=value)


def test_the_message_states_what_is_enforced() -> None:
    """It said `[0, 1]` and accepted 2. A reader who checks against it and passes is
    entitled to believe their input was in range."""
    with pytest.raises(ValueError) as excinfo:
        reject_non_finite(maf=math.nan)
    message = str(excinfo.value)
    assert "finite number" in message
    assert "must be a finite fraction in [0, 1]" not in message
    # ...and it names the legitimate use of an out-of-range value, since that is now the
    # only way to express it.
    assert "turn a criterion off" in message


@pytest.mark.parametrize("value", [2.0, 1.5, -1.0, 0.0, 1.0])
def test_an_out_of_range_threshold_is_accepted(value: float, reference: ReferenceGenome) -> None:
    """Turning a criterion off is a real request, and this repo's own tests make it."""
    search(_SPACER, PAM(pattern="NGG"), reference=reference, mit_threshold=value)


def test_a_cut_off_nothing_can_clear_is_a_headline_note(reference: ReferenceGenome) -> None:
    report = search(
        _SPACER, PAM(pattern="NGG"), reference=reference, cfd_threshold=2, mit_threshold=2
    )
    assert report.n_sites == 0
    assert any("nothing was nominatable" in n for n in headline_notes(report))


def test_turning_one_criterion_off_says_nothing(reference: ReferenceGenome) -> None:
    """The half that must not fire: nomination still happens on the other criterion."""
    report = search(_SPACER, PAM(pattern="NGG"), reference=reference, mit_threshold=1.1)
    assert report.n_sites > 0
    assert not [n for n in headline_notes(report) if "nominatable" in n]


def test_a_maf_no_allele_can_reach_is_a_headline_note(
    reference: ReferenceGenome, tmp_path: Path
) -> None:
    """The mirror on the population axis: the pass ran and admitted nothing by cut-off."""
    from alleleforge.data.gnomad import GnomadDB

    sites = tmp_path / "sites.tsv"
    sites.write_text("#chrom\tpos\tref\talt\taf\tafr\nchr2\t10\tA\tG\t0.02\t0.05\n")
    report = search(
        _SPACER,
        PAM(pattern="NGG"),
        reference=reference,
        gnomad=GnomadDB.from_sites_tsv(sites),
        populations=["afr"],
        maf=2.0,
    )
    assert any("population pass was turned off by the cut-off" in n for n in headline_notes(report))
