"""Three refusals on the off-target path, all of which produce a *confident wrong answer*.

These were invisible to measurement, not merely untested. `tests/offtarget` contains
`test_a_wrong_build_population_file_says_so.py`, which reads `engine.py`'s own source
text; every mutant of `engine.py` reformats that source, so every mutant died for a
reason unrelated to the mutation and the module scored 100%. R689's no-op control
refused to report that number and named the test instead. Excluding that one file made
the module measurable and three `raise` deletions survived — which is the point of the
control: it did not just prevent a false clean score, it uncovered real gaps underneath
one.

What the three have in common is that deleting them does not raise anything later. The
search runs to completion and emits a report with a specificity number on it.

1. **An empty spacer** (`engine.py:149`). Every position of the genome matches an empty
   query, so a blank field or an unset `$SPACER` produced thousands of "off-target
   sites", worst score 1.000, specificity 0.000 — the most alarming report this tool can
   emit, from no input at all. R523 deliberately chose to *label* a too-short query
   rather than refuse it, because screening a seed is legitimate; empty is not that.

2. **An index built for another assembly** (`engine.py:599`). PAMs get anchored over the
   index's sequence while bases and coordinates are read from this reference, so the hits
   are real-looking and at the wrong loci.

3. **An index whose contigs are the wrong length** (`engine.py:609`). The build-label
   comparison in (2) fails *open* when either side is unlabelled — which is exactly the
   index nobody recorded a genome for. This is the fallback that does not depend on a
   name, and it was the one with no test.

(2) and (3) are the same defect reached two ways, and that is why both are pinned: a test
against labelled builds alone leaves the unlabelled case — the likelier one — uncovered.

Found by deleting each refusal (`scripts/mutate.py --mode raise`, with the
source-reading test excluded).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.genome.index import GenomeIndex
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM

_SPACER = "ACGTAACGTTACGTAACGTT"


def _fasta(tmp_path: Path, name: str, *, bases: str, contig: str = "chr1") -> Path:
    path = tmp_path / name
    path.write_text(f">{contig}\n{bases}\n")
    return path


def _genome(length: int, seed: int) -> str:
    import random

    rng = random.Random(seed)
    return "".join(rng.choice("ACGT") for _ in range(length))


# -- 1. the empty query --------------------------------------------------------


@pytest.mark.parametrize("empty", ["", "   ", "\t", "\n"])
def test_an_empty_spacer_is_refused_rather_than_matching_everywhere(
    tmp_path: Path, empty: str
) -> None:
    """Whitespace counts as empty, because a shell is what supplies this field.

    `"$SPACER"` with `SPACER` unset expands to the empty string; a CSV cell or a web
    form supplies a space. All of them mean "nothing was given", and all of them used to
    mean "every position of the genome is a hit".
    """
    reference = ReferenceGenome(_fasta(tmp_path, "ref.fa", bases=_genome(600, 1)), build="hg38")
    with pytest.raises(ValueError, match="spacer is empty"):
        search(empty, PAM(pattern="NGG"), reference=reference)


def test_the_empty_spacer_refusal_says_what_to_supply_instead(tmp_path: Path) -> None:
    """A refusal on a blank field has to say what the field wanted.

    This is the one error a user reaches by supplying *nothing*, so they have no wrong
    value to inspect for a clue. The message names the length, the orientation, and the
    PAM exclusion, because "spacer is empty" alone does not distinguish a spacer from
    the protospacer-plus-PAM a reader is just as likely to paste.
    """
    reference = ReferenceGenome(_fasta(tmp_path, "ref.fa", bases=_genome(600, 1)), build="hg38")
    with pytest.raises(ValueError) as refused:
        search("", PAM(pattern="NGG"), reference=reference)
    message = str(refused.value)

    assert "specificity" in message, (
        "the refusal does not mention the specificity of zero, which is the symptom a "
        "user arrives with and the reason this is an error rather than a caveat",
        message,
    )
    assert "20" in message and "PAM" in message, message


# -- 2 and 3. an index that is not this reference ------------------------------


def test_a_search_is_refused_when_the_index_is_labelled_another_assembly(
    tmp_path: Path,
) -> None:
    """Both builds known and disagreeing: the cheap, name-based check."""
    bases = _genome(600, 7)
    indexed = ReferenceGenome(_fasta(tmp_path, "hg19.fa", bases=bases), build="hg19")
    index = GenomeIndex.build_genome(indexed, cache_dir=tmp_path / "idx")
    # Same sequence, so *only* the labels disagree and nothing else can explain a refusal.
    reference = ReferenceGenome(_fasta(tmp_path, "hg38.fa", bases=bases), build="hg38")

    with pytest.raises(ValueError, match="genome_index was built for assembly") as refused:
        search(_SPACER, PAM(pattern="NGG"), reference=reference, genome_index=index)
    message = str(refused.value)
    assert "hg19" in message and "hg38" in message, (
        "the refusal does not name both assemblies, so the reader cannot tell which of "
        "their two inputs is the wrong one",
        message,
    )


def test_a_search_with_a_matching_build_is_not_refused(tmp_path: Path) -> None:
    """The premise, and the case neither guard may fire on.

    Without this, both refusals above would pass against a seam that rejected every
    index — which would read as "safe" and make the feature unusable.
    """
    bases = _genome(600, 7)
    reference = ReferenceGenome(_fasta(tmp_path, "ref.fa", bases=bases), build="hg38")
    index = GenomeIndex.build_genome(reference, cache_dir=tmp_path / "idx")

    report = search(_SPACER, PAM(pattern="NGG"), reference=reference, genome_index=index)
    assert report is not None


def test_an_unlabelled_index_of_a_different_genome_is_still_refused(
    tmp_path: Path,
) -> None:
    """The guard that does not depend on a name — the one with no test.

    This is the case the label comparison cannot catch and the likelier case in
    practice: an index built from a FASTA nobody recorded a build for. Contig *length*
    is the evidence, and two assemblies do not share one.

    If this regressed, the search would anchor PAMs over one genome's sequence and read
    coordinates from another, and report hits at loci that exist in neither.
    """
    indexed = ReferenceGenome(_fasta(tmp_path, "other.fa", bases=_genome(600, 11)), build=None)
    index = GenomeIndex.build_genome(indexed, cache_dir=tmp_path / "idx")
    # A *different length*, which is what makes them different genomes whatever the label.
    reference = ReferenceGenome(_fasta(tmp_path, "ref.fa", bases=_genome(900, 12)), build=None)

    with pytest.raises(ValueError, match="does not index this reference") as refused:
        search(_SPACER, PAM(pattern="NGG"), reference=reference, genome_index=index)
    message = str(refused.value)
    assert "599" in message or "899" in message or "600" in message or "900" in message, (
        "the refusal does not quote either base count, so a reader cannot check which "
        "input is which",
        message,
    )


def test_the_two_index_guards_are_not_the_same_guard(tmp_path: Path) -> None:
    """Pin that the label path and the length path are reached independently.

    A single test covering a wrong-build *and* wrong-length index would pass with either
    guard deleted. These two assert the distinct messages, so each one's deletion is
    visible: same labels with different lengths must take the length path, and the
    refusal must not be the build-name one.
    """
    indexed = ReferenceGenome(_fasta(tmp_path, "a.fa", bases=_genome(600, 3)), build="hg38")
    index = GenomeIndex.build_genome(indexed, cache_dir=tmp_path / "idx")
    reference = ReferenceGenome(_fasta(tmp_path, "b.fa", bases=_genome(900, 4)), build="hg38")

    with pytest.raises(ValueError) as refused:
        search(_SPACER, PAM(pattern="NGG"), reference=reference, genome_index=index)
    message = str(refused.value)

    assert "does not index this reference" in message, message
    assert "was built for assembly" not in message, (
        "matching labels took the build-name path, so the length check is unreachable "
        "whenever the labels agree — which is the case it exists for",
        message,
    )
