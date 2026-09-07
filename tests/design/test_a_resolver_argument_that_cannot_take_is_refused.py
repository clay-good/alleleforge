"""`design()` silently dropped every resolver argument for an already-resolved variant.

`design()` accepts `clinvar`, `dbsnp`, `hgvs` and `effect` — the four backends the
resolver consults — and forwards them to `resolve()`. But when `inp` is already a
`ResolvedVariant`, resolution is skipped, and the four arguments went nowhere. No
error, no note: the menu came back looking exactly like a menu that had asked for
them and found nothing.

`effect` is the one that bites. A supplied effect predictor annotates the menu with
the variant's predicted consequence, and raises the "you are correcting a variant
predicted to have modifier impact" caution. Pass a resolved variant and you get a
menu with neither, indistinguishable from a run where the predictor said nothing was
notable. The project's own CLI is how this was found: `aforge design` resolves the
variant itself, so no `--vep`-style flag could ever have worked there.

Unlike `cell_context` (see `test_an_unconsumed_cell_context_says_so`), which one
vertical does consume and so earns a note, these four are consumed by nothing at all
on this path. There is no reading of the call under which they do something, so this
is a caller mistake with a remedy, and it is refused rather than annotated.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent
from alleleforge.variant.effect import Consequence, Impact, StaticEffectPredictor, VariantEffect
from alleleforge.variant.resolver import resolve

_CONTIG = "T" * 20 + "ACGTAACGTTACGTAACGTT" + "TGG" + "T" * 20


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    fasta = tmp_path / "ref.fa"
    fasta.write_text(f">chr2\n{_CONTIG}\n", encoding="utf-8")
    return ReferenceGenome(fasta, build="hg38")


def _variant() -> str:
    return f"chr2:26:{_CONTIG[25]}>G"


#: `str(Variant)` is 0-based, while the `chr:pos:ref>alt` input form is 1-based, so
#: the table is keyed off the resolved variant rather than the string handed to
#: `resolve()`.
_KEY = f"chr2:25:{_CONTIG[25]}>G"


def _predictor() -> StaticEffectPredictor:
    return StaticEffectPredictor(
        {
            _KEY: VariantEffect(
                consequence=Consequence.MISSENSE,
                impact=Impact.MODERATE,
                gene="TESTG",
                transcript="ENST00000000001",
            )
        }
    )


def test_a_resolver_backend_is_refused_when_the_variant_is_already_resolved(
    reference: ReferenceGenome,
) -> None:
    resolved = resolve(_variant(), build="hg38", reference=reference)
    with pytest.raises(ValueError) as excinfo:
        design(
            resolved,
            reference=reference,
            intent=EditIntent.CORRECT,
            effect=_predictor(),
            run_offtarget=False,
        )
    message = str(excinfo.value)
    assert "effect" in message, "the refusal must name the argument that was dropped"
    assert "resolve" in message, "the refusal must point at where the argument does take"


def test_the_refusal_names_every_dropped_backend(reference: ReferenceGenome) -> None:
    resolved = resolve(_variant(), build="hg38", reference=reference)
    with pytest.raises(ValueError) as excinfo:
        design(
            resolved,
            reference=reference,
            effect=_predictor(),
            clinvar=object(),  # type: ignore[arg-type]
            run_offtarget=False,
        )
    message = str(excinfo.value)
    for name in ("clinvar", "effect"):
        assert name in message, f"{name} was dropped but not named"
    for name in ("dbsnp", "hgvs"):
        assert name not in message, f"{name} was not passed and must not be named"


def test_an_unresolved_input_still_consumes_the_effect_predictor(
    reference: ReferenceGenome,
) -> None:
    """The refusal must not cost the working path: an unresolved input still annotates."""
    menu = design(
        _variant(),
        reference=reference,
        intent=EditIntent.CORRECT,
        effect=_predictor(),
        run_offtarget=False,
    )
    assert "missense" in menu.rationale.lower(), (
        "a resolvable input with an effect predictor must carry the consequence note"
    )
