"""Telling a caller an ancestry was not examined must say what *was* available.

`docs/data.md` documents three ancestry vocabularies — gnomAD's lowercase (`afr`),
1000 Genomes' uppercase super-populations (`AFR`), and HGDP's regions (`africa`). A
caller who reads that page, types `--populations AFR`, and hands over a gnomAD slice
whose columns are `afr` and `nfe` is told:

    no supplied source carries data for AFR — those ancestries were requested but not
    examined, and their absence from the breakdown means 'no data', not 'no risk'

Every word true, and unactionable. The report knows exactly which labels the supplied
sources carry — it computed the `backed` set to decide this very sentence — and did not
say. That is the shape an earlier round fixed in the CLI help: a warning that sends the
reader looking for something without telling them where.

The labels are deliberately **not** case-folded together. gnomAD's `afr` and 1000
Genomes' `AFR` are different groupings of different cohorts, and quietly answering a
question about one with data about the other is exactly the kind of substitution this
project refuses elsewhere. Naming the available labels lets the caller make that choice;
matching them for them would make it invisible.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.data.gnomad import GnomadDB
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM

SPACER = "TATATATATATACCAATATA"


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    return ReferenceGenome(fasta)


@pytest.fixture
def gnomad(tmp_path: Path) -> GnomadDB:
    sites = tmp_path / "sites.tsv"
    sites.write_text("#chrom\tpos\tref\talt\taf\tafr\tnfe\n" + "chr2\t45\tT\tA\t0.20\t0.30\t0.10\n")
    return GnomadDB.from_sites_tsv(sites)


def _description(reference: ReferenceGenome, **kwargs: object) -> str:
    report = search(SPACER, PAM(pattern="NGG"), reference=reference, **kwargs)  # type: ignore[arg-type]
    return report.search_description()


def test_the_available_labels_are_named(reference: ReferenceGenome, gnomad: GnomadDB) -> None:
    text = _description(reference, gnomad=gnomad, populations=["AFR"])
    assert "no supplied source carries data for AFR" in text
    assert "afr" in text and "nfe" in text
    assert "carry" in text or "carries" in text


def test_a_backed_request_says_nothing_extra(reference: ReferenceGenome, gnomad: GnomadDB) -> None:
    """The addition must not fire when every requested ancestry is available."""
    text = _description(reference, gnomad=gnomad, populations=["afr"])
    assert "requested but not examined" not in text


def test_with_no_source_at_all_there_is_nothing_to_offer(reference: ReferenceGenome) -> None:
    """`--populations` with no ancestry source: still disclosed, no false suggestion.

    Naming an empty list of alternatives would read as "these exist and yours is not
    among them", when the truth is that nothing was supplied.
    """
    text = _description(reference, populations=["afr"])
    assert "requested but not examined" in text
    assert "no ancestry source was supplied" in text


def test_the_labels_are_not_case_folded(reference: ReferenceGenome, gnomad: GnomadDB) -> None:
    """`AFR` must not be answered with `afr` data; they are different groupings."""
    text = _description(reference, gnomad=gnomad, populations=["AFR"])
    assert "no supplied source carries data for AFR" in text
