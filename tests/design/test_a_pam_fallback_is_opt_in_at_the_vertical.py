"""The PAM-flexible fallbacks were opt-in everywhere except in their own signature.

`allow_ng` and `allow_spry` widen SpCas9 nuclease design beyond the canonical `NGG` PAM:
with them, a site that has no actionable `NGG` guide can still be targeted with an
SpCas9-NG or SpRY guide. That is a scientific choice with a specificity cost — a
PAM-flexible nuclease has more genomic matches — which is why both default to `False` and
why a candidate found that way carries a `relaxed-pam:` flag.

Every caller passed them explicitly. `design()` forwards the user's flags to the nuclease
vertical, the CLI has a switch for each, and the web schema exposes both — so flipping
`design_cas9`'s own declared defaults to `True` changed no shipped behaviour and left the
whole suite green. The only caller who reaches those defaults is a library caller who
omits the keyword, and for them the mutation is silent: a menu of PAM-flexible guides,
each correctly flagged, offered for a locus where the canonical nuclease found nothing —
and nothing in the output says the widening was never requested.

Found by flipping the defaults (`scripts/mutate.py --mode dflt`); both survived.

The fixture is the point. `SPACER` is chosen with no `GG` and no `CC`, so neither strand
carries an `NGG` PAM, and the PAM slot after the spacer is `TGA` — an `NG` match that is
not an `NGG` one. That makes "no canonical guide, but a relaxed one is available" the
state under test, which is the only state in which these flags do anything at all. A
contig that simply has no PAM of any kind, which is the existing fallback fixture, cannot
distinguish the defaults: every setting returns an empty menu.
"""

from __future__ import annotations

from collections.abc import Callable

from alleleforge.design.cas9 import design_cas9
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.scoring.cas9_efficiency import RuleSet3Scorer
from alleleforge.types.candidate import DesignCandidate
from alleleforge.types.edit import EditIntent
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.variant.resolver import resolve

from .conftest import PAD, SPACER

MakeRef = Callable[[dict[str, str]], ReferenceGenome]

#: An `NG` PAM that is not an `NGG` one, in the slot immediately after the spacer.
_NG_ONLY_PAM = "TGA"


def _ng_only_reference(make_reference: MakeRef) -> ReferenceGenome:
    return make_reference({"chr2": PAD + SPACER + _NG_ONLY_PAM + PAD})


def _design(ref: ReferenceGenome, **kw: object) -> list[DesignCandidate]:
    base = str(ref.fetch(GenomicInterval(chrom="chr2", start=32, end=33, strand=Strand.PLUS)))
    resolved = resolve(f"chr2:33:{base}>G", reference=ref)
    return design_cas9(
        resolved,
        EditIntent.CORRECT,
        reference=ref,
        efficiency_scorer=RuleSet3Scorer(),
        run_offtarget=False,
        **kw,
    )


def _relaxed(candidates: list[DesignCandidate]) -> list[str]:
    return [f for c in candidates for f in c.flags if f.startswith("relaxed-pam")]


def test_the_fixture_offers_a_relaxed_guide_when_asked(make_reference: MakeRef) -> None:
    """Premise: with the flag on, this locus does yield a PAM-flexible candidate.

    Without this the two tests below would pass on a fixture that yields nothing for any
    setting, which is how a fallback flag comes to be "tested" by a case that cannot see
    it.
    """
    assert _relaxed(_design(_ng_only_reference(make_reference), allow_ng=True))


def test_no_relaxed_guide_is_offered_by_default(make_reference: MakeRef) -> None:
    """Omitting both keywords must leave the canonical PAM in force."""
    assert not _relaxed(_design(_ng_only_reference(make_reference))), (
        "design_cas9 offered a PAM-flexible candidate to a caller who did not ask for "
        "one; allow_ng/allow_spry must default to the canonical NGG PAM"
    )


def test_spry_is_also_opt_in(make_reference: MakeRef) -> None:
    """`allow_spry` is the more permissive of the two, so it is checked separately.

    `NRN`/`NYN` matches almost anywhere, so a flipped `allow_spry` default widens design
    at loci where even the `NG` fallback finds nothing — a strictly larger blast radius
    than `allow_ng`, and invisible in exactly the same way.
    """
    flat = make_reference({"chr9": "A" * 400})
    base = str(flat.fetch(GenomicInterval(chrom="chr9", start=200, end=201, strand=Strand.PLUS)))
    resolved = resolve(f"chr9:201:{base}>G", reference=flat)
    by_default = design_cas9(
        resolved,
        EditIntent.CORRECT,
        reference=flat,
        efficiency_scorer=RuleSet3Scorer(),
        run_offtarget=False,
    )
    assert not _relaxed(by_default)
    assert not by_default, (
        "a contig with no PAM of any kind yielded candidates by default; the SpRY "
        "fallback must be opt-in"
    )
