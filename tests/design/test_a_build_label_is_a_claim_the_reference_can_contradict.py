"""`design(build=...)` and the reference's own label could disagree, silently.

`build` says which assembly the input's coordinates are in. A `ReferenceGenome` carries
the assembly it *is*. When the two disagreed, exactly one was wrong and nothing said so:
resolution used the argument, the provenance recorded `reference.build or build` — the
reference's — and the run came back stamped with an assembly it had not been asked for.

The default made the reverse case worse. `build` defaulted to the string `"hg38"`, so a
caller who labelled their genome `mm39` and never touched `build` was resolving against
"hg38" on every call, which is the whole of what a ClinVar or dbSNP lookup keys on.

Same shape as `chromatin_track` without `encode_tracks` a few rounds earlier: two inputs
that only mean something together, and a combination the library answered instead of
refusing. The web API had its own copy of this and was fixed one round before the library
it is supposed to be a thin shell over.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import BUILTIN_BUILDS, ReferenceGenome
from alleleforge.types.variant import _ASSEMBLY_ALIASES, assembly_matches, canonical_assembly

SPACER = "ACGTAACGTTACGTAACGTT"


@pytest.fixture
def make_labelled(tmp_path: Path) -> Callable[[str | None], ReferenceGenome]:
    """Return a factory for a designable reference carrying the label asked for."""
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    counter = {"n": 0}

    def _make(build: str | None) -> ReferenceGenome:
        counter["n"] += 1
        fasta = tmp_path / f"ref{counter['n']}.fa"
        fasta.write_text(">chr2\n" + "".join(seq) + "\n")
        return ReferenceGenome(fasta, build=build)

    return _make


def test_a_build_the_reference_contradicts_is_refused(
    make_labelled: Callable[[str | None], ReferenceGenome],
) -> None:
    with pytest.raises(ValueError) as exc:
        design("chr2:71:A>C", reference=make_labelled("hg38"), build="hg19", run_offtarget=False)
    message = str(exc.value)
    assert "hg19" in message and "hg38" in message


def test_the_reference_label_is_the_default_not_the_string_hg38(
    make_labelled: Callable[[str | None], ReferenceGenome],
) -> None:
    """A caller who never passes `build` gets the assembly they actually loaded."""
    menu = design("chr2:71:A>C", reference=make_labelled("mm39"), run_offtarget=False)
    assert menu.provenance.reference_build == "mm39"


def test_an_unlabelled_reference_still_defaults_to_hg38(
    make_labelled: Callable[[str | None], ReferenceGenome],
) -> None:
    """The documented default, for a reference that says nothing about itself."""
    menu = design("chr2:71:A>C", reference=make_labelled(None), run_offtarget=False)
    assert menu.provenance.reference_build == "hg38"


def test_an_agreeing_build_in_another_spelling_is_accepted(
    make_labelled: Callable[[str | None], ReferenceGenome],
) -> None:
    menu = design(
        "chr2:71:A>C", reference=make_labelled("hg38"), build="GRCh38", run_offtarget=False
    )
    assert menu.provenance.reference_build == "GRCh38"


def test_two_spellings_of_an_unaliased_assembly_are_one_assembly() -> None:
    """The fallback returned the name as written, so case decided identity.

    Aliased names have always compared case-insensitively, because the lookup lowercases.
    An assembly the table does not know — a patch release, a plant genome, an internal
    build — compared by exact spelling, and `assembly_matches` returning False is read
    everywhere as "these coordinates are in different assemblies": a refused design here,
    a rejected genome index in the off-target engine.
    """
    assert assembly_matches("GRCh38.p14", "grch38.p14")
    assert canonical_assembly("  Sorghum_v3  ") == canonical_assembly("sorghum_v3")
    assert not assembly_matches("GRCh38.p14", "GRCh37.p13")


def test_every_built_in_build_is_known_to_the_comparison() -> None:
    """The alias table is hand-written; the builds it must cover are not.

    A build added to `BUILTIN_BUILDS` and not to the table compares by spelling alone, so
    the download's own name and the name a user types for it are two assemblies.
    """
    unknown = sorted(
        desc.name for desc in BUILTIN_BUILDS.values() if desc.name.lower() not in _ASSEMBLY_ALIASES
    )
    assert not unknown, f"built-in builds the assembly comparison does not know: {unknown}"


def test_no_alias_key_is_unreachable() -> None:
    """The lookup lowercases its key, so a capitalized entry can never be hit."""
    unreachable = sorted(key for key in _ASSEMBLY_ALIASES if key != key.lower())
    assert not unreachable, f"alias keys nothing can ever look up: {unreachable}"
